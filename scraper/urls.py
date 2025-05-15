
from django.urls import path
from .views import MovieListAPIView, TriggerScraperAPIView, ScraperProgressView

urlpatterns = [
    path('start/', TriggerScraperAPIView.as_view(), name='start-scraper'),
    path('progress/<uuid:job_id>/', ScraperProgressView.as_view(), name='scraper-progress'),
    path('movies/', MovieListAPIView.as_view(), name='scraper-movie-list'),
]
