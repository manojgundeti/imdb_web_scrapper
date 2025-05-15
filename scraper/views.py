from django.shortcuts import render

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import uuid
from django.http import JsonResponse
from django.views import View
from threading import Thread
from django.core import management
from scraper.models import ScraperStatus
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from scraper.models import Movie
from scraper.serializers import MovieSerializer
from django.db.models import Q

@api_view(['GET'])
def movie_list_api(request):
    query = request.GET.get('search', '')
    per_page = int(request.GET.get('per_page', 10))

    movies = Movie.objects.all().order_by('-id')

    if query:
        movies = movies.filter(
            Q(title__icontains=query) |
            Q(directors__icontains=query) |
            Q(cast__icontains=query) |
            Q(year__icontains=query)
        )

    paginator = PageNumberPagination()
    paginator.page_size = per_page
    result_page = paginator.paginate_queryset(movies, request)
    serializer = MovieSerializer(result_page, many=True)
    return paginator.get_paginated_response(serializer.data)

class ScraperProgressView(View):
    def get(self, request, job_id):
        job_uuid = job_id
        status = get_object_or_404(ScraperStatus, job_id=job_uuid)
        return JsonResponse({
            "job_id": str(status.job_id),
            "status": status.status,
            "scraped": status.scraped_movies,
            "total": status.total_movies,
            "error": status.error_message,
            "updated_at": status.updated_at
        })
@method_decorator(csrf_exempt, name='dispatch')
class TriggerScraperView(View):
    def post(self, request):
        search_type = request.POST.get('type')
        search_value = request.POST.get('value')
        limit = int(request.POST.get('limit', 10))

        # Create a job ID
        status = ScraperStatus.objects.create(
            status="pending",
            total_movies=limit
        )
        job_id = str(status.job_id)

        def run_scraper():
            try:
                management.call_command(
                    'scrapper',
                    type=search_type,
                    value=search_value,
                    limit=limit,
                    job_id=job_id
                )
            except Exception as e:
                status.status = "error"
                status.error_message = str(e)
                status.save(update_fields=["status", "error_message"])

        Thread(target=run_scraper).start()

        return JsonResponse({"status": "started", "job_id": job_id})
