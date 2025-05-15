from django.shortcuts import render
from rest_framework.views import APIView
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
from scraper.serializers import MovieSerializer, ScraperStatusSerializer, ScraperTriggerSerializer
from django.db.models import Q
from rest_framework import status as drf_status

class MovieListAPIView(APIView):
    def get(self, request):
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


class ScraperProgressView(APIView):
    def get(self, request, job_id):
        status_obj = get_object_or_404(ScraperStatus, job_id=job_id)
        serializer = ScraperStatusSerializer(status_obj)
        return Response(serializer.data)

class TriggerScraperAPIView(APIView):
    def post(self, request):
        serializer = ScraperTriggerSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=drf_status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        search_type = data['type']
        search_value = data['value']
        limit = data.get('limit', 50)

        status_obj = ScraperStatus.objects.create(
            status="pending",
            total_movies=limit
        )
        job_id = str(status_obj.job_id)

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
                status_obj.status = "error"
                status_obj.error_message = str(e)
                status_obj.save(update_fields=["status", "error_message"])

        Thread(target=run_scraper).start()

        return Response({"status": "started", "job_id": job_id}, status=drf_status.HTTP_202_ACCEPTED)
