# IMDb Movie Scraper (Django + Playwright + BeautifulSoup)

This project is a Django-based web scraper that fetches movie data from IMDb based on **genre** or **keyword**. It uses :
-  **Playwright (async)** for dynamic page rendering and JavaScript interaction
-  **BeautifulSoup** for HTML parsing
-  **Django ORM** for storing data
-  **Multithreading** to run scraping jobs in the background
-  **Asynchronous programming** to ensure responsive, non-blocking behavior during scraping

---

## Features

- Scrapes IMDb movies using a **genre** or a **keyword**
- Extracts:
  - Title
  - Release Year
  - IMDb Rating
  - Directors / Creators
  - Cast
  - Plot Summary
- Uses **async/await** with Playwright for efficient page scraping
- Background job execution with **Python threading** (non-blocking)
- Tracks job progress using the `ScraperStatus` model (with job UUIDs)
- Stores movie data in the `Movie` model
- Batch inserts and intelligently updates existing records
- REST API endpoints for:
  - Triggering the scraper
  - Tracking job status
  - Listing scraped movies with search and pagination

---

## Installation

```bash
# Create virtual environment
python -m venv imdb_env
source imdb_env/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright Chromium browser
playwright install chrome
```

---

## Django Setup

### Run Migrations

```bash
python manage.py migrate
```

---

## Run the Scraper from CLI

```bash
python manage.py scrapper --type genre --value action --limit 100
```
this command uses `asyncio` with Playwright and progressbar with tqdm

---

## Run Development Server

```bash
python manage.py runserver
```

---

## API Endpoints

### 1. Trigger Scraper
- **Method:** `POST`
- **URL:** `/scraper/start/`

#### Request Body:
```json
{
  "type": "genre",       // or "keyword"
  "value": "action",     // the genre or keyword to scrape
  "limit": 20            // number of movies to scrape
}
```

#### Example Response:
```json
{
  "status": "started",
  "job_id": "uuid-value"
}
```

---

### 2. Get Scraper Job Status
- **Method:** `GET`
- **URL:** `/scraper/status/<job_id>/`

#### Example Response:
```json
{
  "job_id": "uuid-value",
  "status": "completed",
  "scraped": 20,
  "total": 20,
  "error": null,
  "updated_at": "2025-05-15T12:34:56Z"
}
```

---

### 3. List Movies
- **Method:** `GET`
- **URL:** `/movies/?search=batman&per_page=5`

#### Query Parameters:
- `search` – (optional) search term for title, cast, director, or year
- `per_page` – number of results per page (default: `50`)

#### Example Response:
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "title": "The Dark Knight",
      "year": "2008",
      "rating": "9.0",
      "directors": "Christopher Nolan",
      "cast": "Christian Bale, Heath Ledger",
      "plot": "Batman raises the stakes in his war on crime..."
    }
  ]
}
```

---


