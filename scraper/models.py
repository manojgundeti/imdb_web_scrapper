import uuid
from django.db import models

# Create your models here.
class Movie(models.Model):
    title = models.CharField(max_length=255,unique=True)
    year = models.IntegerField(null=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1, null=True)
    directors = models.TextField(null=True)
    cast = models.TextField(null=True)
    plot = models.TextField(null=True)
    # url = models.URLField(unique=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.year})"

class ScraperStatus(models.Model):
    job_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    total_movies = models.IntegerField(default=0)
    scraped_movies = models.IntegerField(default=0)
    status = models.CharField(max_length=20, choices=[
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("error", "Error")
    ], default="pending")
    error_message = models.TextField(blank=True, null=True)


    def __str__(self):
        return f"Job {self.job_id} - {self.status}"
