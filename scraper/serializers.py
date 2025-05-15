# scraper/serializers.py

from rest_framework import serializers
from scraper.models import Movie

class MovieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Movie
        fields = ['id', 'title', 'year', 'rating', 'directors', 'cast', 'plot']
