# scraper/urls.py

from django.urls import path
from .views import TriggerScraperView, ScraperProgressView, movie_list_api

urlpatterns = [
    path('scraper/start/', TriggerScraperView.as_view(), name='start-scraper'),
    path('scraper/progress/<uuid:job_id>/', ScraperProgressView.as_view(), name='scraper-progress'),
    path('api/movies/', movie_list_api, name='api-movie-list'),
]
