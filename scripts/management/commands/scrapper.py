import asyncio
import logging
import os
import re
import sys
import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError
from playwright.async_api import async_playwright,TimeoutError, Error as PlaywrightError
import math
from asgiref.sync import sync_to_async
from tqdm.asyncio import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from scraper.models import ScraperStatus
import uuid

from scraper.models import Movie
HEADERS = {'User-Agent': 'Mozilla/5.0'}
logger = logging.getLogger(__name__)
IMDB_PAGE_SIZE = 50
SEARCH_CHOICES = ['genre', 'keyword']
BATCH_SIZE = 2

class Command(BaseCommand):
    help = 'Scrapes IMDb movies based on genre or keyword'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=SEARCH_CHOICES,
            required=True,
            help=f"Specify search type: {' or '.join(SEARCH_CHOICES)}"
        )
        parser.add_argument(
            '--value',
            type=str,
            required=True,
            help=f"The actual {' or '.join(SEARCH_CHOICES)} to search"
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=IMDB_PAGE_SIZE,
            help='Number of movies to scrape'
        )
        parser.add_argument(
            '--job_id',
            type=str,
            required=False,
            help='Job UUID for progress tracking'
        )

    def handle(self, *args, **options):
        search_type = options['type']
        search_value = options['value']
        limit = options['limit']
        job_id = options.get('job_id')
        if job_id:
            try:
                status = ScraperStatus.objects.get(job_id=uuid.UUID(job_id))
            except ScraperStatus.DoesNotExist:
                raise CommandError(f"Job with id {job_id} does not exist.")
        else:
            status = ScraperStatus.objects.create()
        status.status = 'running'
        status.save(update_fields=["status"])

        if search_type not in SEARCH_CHOICES:
            status.status = 'error'
            status.error_message = f"Invalid type. Choose either {' or '.join(SEARCH_CHOICES)}."
            status.save(update_fields=["status", "error_message"])
            raise CommandError(status.error_message)

        print(f"Scraping IMDb using {search_type}: '{search_value}', limit: {limit}")
        try:
            asyncio.run(self.scrape_movies(search_type, search_value, limit, status))
        except Exception as e:
            status.status = 'error'
            status.error_message = f"An error occurred: {e}"
            status.save(update_fields=["status", "error_message"])
            raise
    @sync_to_async
    def update_status(self, status_obj, **fields):
        for key, value in fields.items():
            setattr(status_obj, key, value)
        status_obj.save(update_fields=list(fields.keys()))

    @sync_to_async
    def bulk_insert_movies(self, batch):
        existing_titles = set(Movie.objects.filter(title__in=[m.title for m in batch]).values_list('title', flat=True))

        to_update = [m for m in batch if m.title in existing_titles]
        to_create = [m for m in batch if m.title not in existing_titles]

        if to_create:
            Movie.objects.bulk_create(to_create, ignore_conflicts=True)

        if to_update:
            # Fetch the existing objects
            existing_movies = {m.title: m for m in Movie.objects.filter(title__in=[m.title for m in to_update])}
            for m in to_update:
                existing = existing_movies.get(m.title)
                if existing:
                    existing.year = m.year
                    existing.rating = m.rating
                    existing.directors = m.directors
                    existing.cast = m.cast
                    existing.plot = m.plot
            Movie.objects.bulk_update(existing_movies.values(), ['year', 'rating', 'directors', 'cast', 'plot'])

        # Movie.objects.bulk_create(batch, ignore_conflicts=True)

    async def scrape_movies(self, search_type, search_value, limit,status):

        search_value = search_value.strip().replace(" ", "-")
        if search_type == "genre":
            url = f"https://www.imdb.com/search/title/?genres={search_value}"
        else:  # keyword
            url = f"https://www.imdb.com/search/title/?keywords={search_value}&explore=keywords"

        try:
            movie_links = await self.fetch_movie_list_page(url, limit)
        except Exception as e:
            await self.update_status(status, status='error', error_message=f"Error fetching movie list: {e}")
            raise
        print(f"Total movies found: {len(movie_links)}")
        movie_instances = []
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {pool.submit(self.scrape_movie_details, link): link for link in movie_links}

            for future in tqdm(as_completed(futures), total=len(futures), desc="Scraping progress"):
                try:
                    movie_data = future.result()
                except Exception as e:
                    logger.warning(f"Error scraping {futures[future]}: {e}")
                    continue

                if not movie_data:
                    continue

                movie = Movie(
                    title=movie_data['title'],
                    year=movie_data['year'],
                    rating=float(movie_data['rating']) if movie_data['rating'] else None,
                    directors=movie_data['directors'],
                    cast=movie_data['cast'],
                    plot=movie_data['plot'],
                    # url=movie_data['url']
                )
                movie_instances.append(movie)

            if len(movie_instances) >= BATCH_SIZE:
                await self.bulk_insert_movies(movie_instances)
                movie_instances.clear()

        if movie_instances:
            await self.bulk_insert_movies(movie_instances)
        if len(movie_links) == 0:
            await self.update_status(status, status='error', error_message="No movies found")
            return
        await self.update_status(status, status='completed', scraped_movies=len(movie_links))
    async def fetch_movie_list_page(self, url,limit):
        try:
            all_links = []
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.set_extra_http_headers(HEADERS)
                await page.goto(url)

                previous_height = 0
                if limit < 50:
                    max_iterations = 0
                else:
                    max_iterations = math.ceil(int(limit)/50)
                current_iteration = 0
                while True:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(1)
                    current_height = await page.evaluate("document.body.scrollHeight")
                    if current_height == previous_height:
                        if current_iteration == max_iterations:
                            break
                        else:
                            current_iteration += 1
                            try:
                                await page.click(".ipc-see-more__text", timeout=3000)
                            except TimeoutError:
                                logger.info("See more button not found or not clickable.")
                    previous_height = current_height

                html = await page.content()
                await browser.close()

            soup = BeautifulSoup(html, 'html.parser')
            movie_containers = soup.select('ul.ipc-metadata-list')
            current_link_count = 1
            for ul in movie_containers:
                lis = ul.find_all('li', recursive=False)
                for li in lis:
                    link_tag = li.find('a', class_='ipc-title-link-wrapper')
                    if link_tag and 'href' in link_tag.attrs:
                        all_links.append("https://www.imdb.com" + link_tag['href'])
                        if current_link_count == limit:
                            break
                        current_link_count = current_link_count+1
            return all_links
        except TimeoutError:
            logging.error(f"Timeout while navigating to {url}")
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            logger.error(f"Type : {exc_type}, file name : {fname}, line no:  {exc_tb.tb_lineno}")
            return []
        except PlaywrightError as e:
            logging.error(f"Playwright error while navigating to {url}: {e}")
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            logger.error(f"Type : {exc_type}, file name : {fname}, line no:  {exc_tb.tb_lineno}")
            return []



    def scrape_movie_details(self, movie_url):
        # movie_url = "https://www.imdb.com/title/tt0017925/?ref_=nv_sr_srsg_0_tt_8_nm_0_in_0_q_The%2520General%2520(1926)"
        try:
            response = requests.get(movie_url, headers=HEADERS)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            title = soup.find('h1', {'data-testid': 'hero__pageTitle'})
            title = title.get_text(strip=True) if title else None

            year_element = soup.find('ul', {'class': 'ipc-inline-list ipc-inline-list--show-dividers sc-103e4e3c-2 cMcwpt baseAlt baseAlt'}) if soup.find('ul', {'class': 'ipc-inline-list ipc-inline-list--show-dividers sc-103e4e3c-2 cMcwpt baseAlt baseAlt'}) else None
            li_tags = year_element.find_all('li') if year_element else []
            release_year = next(
                                (re.search(r'\d{4}', tag.text.strip()).group() for tag in li_tags[:2] if re.search(r'\d{4}', tag.text.strip())),
                                    None
                                        )
            rating_el = soup.find('div', {'data-testid': 'hero-rating-bar__aggregate-rating__score'})
            imdb_rating = rating_el.find('span').get_text(strip=True) if rating_el else None
            director_el = soup.find('span', string=lambda s: s in ['Director', 'Directors'] if s else False)
            directors = None
            if director_el:
                principal_li = director_el.find_parent('li')
                if principal_li:
                    a_tags = principal_li.select('ul li a')
                    names = [a.get_text(strip=True) for a in a_tags]
                    directors = ", ".join(names) if names else None

            plot_el = soup.find('span', {'data-testid': 'plot-xl'})
            plot_summary = plot_el.get_text(strip=True) if plot_el else None
            if not directors:
                for i in ['Creator','Creators']:
                    directors = self.get_credits_details(soup, i)
                    if directors:
                        break

            cast = self.get_credits_details(soup, 'Stars')

            return {
                'title': title,
                'year': release_year,
                'rating': imdb_rating,
                'directors': directors,
                'cast': cast,
                'plot': plot_summary,
                'url': movie_url
            }
        except requests.RequestException as e:
            logger.warning(f"Failed to fetch {movie_url}: {e}")
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            logger.warning(f"Type : {exc_type}, file name : {fname}, line no:  {exc_tb.tb_lineno}")
            return {}

    def get_credits_details(self,soup, key):
        credits_section = soup.find('a', {'aria-label': 'See full cast and crew'}, href=True, string=key)
        credits_list = []
        if credits_section:
            credits_ul = credits_section.find_next('ul')
            if credits_ul:
                credits_list = [a.text for a in credits_ul.find_all('a')]
        return ", ".join(credits_list) if credits_list else None