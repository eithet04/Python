from django.db import models
from django.contrib.auth.models import User


class BusStop(models.Model):
    """Represents a bus stop."""
    name_mm = models.CharField(max_length=255, verbose_name="Stop Name (Myanmar)")
    name_en = models.CharField(max_length=255, verbose_name="Stop Name (English)")
    # UPDATED: Added road_name fields to differentiate stops with same name
    road_name_mm = models.CharField(max_length=255, blank=True, null=True, verbose_name="Road Name (Myanmar)")
    road_name_en = models.CharField(max_length=255, blank=True, null=True, verbose_name="Road Name (English)")

    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Latitude")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Longitude")

    def __str__(self):
        # UPDATED: Include road name in string representation if available
        if self.road_name_en:
            return f"{self.name_en} ({self.road_name_en})"
        return self.name_en

    class Meta:
        verbose_name = "Bus Stop"
        verbose_name_plural = "Bus Stops"
        # UPDATED: Unique together constraint to handle duplicate stop names on different roads
        unique_together = (('name_mm', 'road_name_mm'), ('name_en', 'road_name_en'))


class BusLine(models.Model):
    """Represents a bus line. E.g., Bus Line 36."""
    line_number = models.IntegerField(unique=True, verbose_name="Bus Line Number")
    description = models.TextField(blank=True, verbose_name="Description")

    def __str__(self):
        # The line below has been corrected
        return str(self.line_number)

    class Meta:
        verbose_name = "Bus Line"
        verbose_name_plural = "Bus Lines"


class RouteSegment(models.Model):
    """Represents a segment of a bus route between two stops."""
    bus_line = models.ForeignKey(BusLine, on_delete=models.CASCADE, related_name='route_segments',
                                 verbose_name="Bus Line")
    bus_stop = models.ForeignKey(BusStop, on_delete=models.CASCADE, related_name='route_segments',
                                 verbose_name="Bus Stop")
    order = models.IntegerField(verbose_name="Stop Order")  # Order of the stop on the route

    # UPDATED: Removed distance_to_next_stop_km and estimated_time_to_next_stop_minutes
    # These will be dynamically calculated using a routing API.

    class Meta:
        ordering = ['bus_line', 'order']
        unique_together = ('bus_line', 'bus_stop', 'order')  # Order of a stop must be unique within a bus line
        verbose_name = "Route Segment"
        verbose_name_plural = "Route Segments"

    def __str__(self):
        return f"{self.bus_line.line_number}: {self.bus_stop.name_en} (Order: {self.order})"


class UserProfile(models.Model):
    """Extends the built-in User model with additional fields."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    preferred_language = models.CharField(max_length=10, choices=[
        ('en', 'English'),
        ('mm', 'Myanmar'),
    ], default='en')

    def __str__(self):
        return f"{self.user.username}'s Profile"

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"


class SavedRoute(models.Model):
    """Allows users to save their favorite or frequently used routes."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_routes')
    start_stop = models.ForeignKey(BusStop, on_delete=models.CASCADE, related_name='routes_as_start')
    end_stop = models.ForeignKey(BusStop, on_delete=models.CASCADE, related_name='routes_as_end')
    name = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}: {self.start_stop.name_en} to {self.end_stop.name_en}"

    class Meta:
        verbose_name = "Saved Route"
        verbose_name_plural = "Saved Routes"
        ordering = ['-created_at']

class RouteSearch(models.Model):
    start_stop = models.ForeignKey(BusStop, related_name='searches_as_start', on_delete=models.CASCADE)
    end_stop = models.ForeignKey(BusStop, related_name='searches_as_end', on_delete=models.CASCADE)
    search_time = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Search from {self.start_stop.name_en} to {self.end_stop.name_en}"
