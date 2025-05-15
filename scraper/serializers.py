

from rest_framework import serializers
from scraper.models import Movie, ScraperStatus

class MovieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movie
        fields = ['id', 'title', 'year', 'rating', 'directors', 'cast', 'plot']

class ScraperStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScraperStatus
        fields = ['job_id', 'status', 'scraped_movies', 'total_movies', 'error_message', 'updated_at']

class ScraperTriggerSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=['genre', 'keyword'])
    value = serializers.CharField()
    limit = serializers.IntegerField(default=50, required=False)
