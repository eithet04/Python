from django.contrib import admin
import requests
from .models import BusStop, BusLine, RouteSegment, UserProfile, SavedRoute


@admin.register(BusStop)
class BusStopAdmin(admin.ModelAdmin):
    # UPDATED: Added road_name fields to list_display
    list_display = ('name_mm', 'name_en', 'road_name_mm', 'road_name_en', 'latitude', 'longitude')
    # UPDATED: Added road_name fields to search_fields
    search_fields = ('name_mm', 'name_en', 'road_name_mm', 'road_name_en')

    def save_model(self, request, obj, form, change):
        """
        Overrides save_model to automatically populate latitude and longitude
        using Nominatim (OpenStreetMap) API if they are not provided.
        It now considers the road name for a more specific search.
        """
        if not obj.latitude or not obj.longitude:
            # Use English name and road name for geocoding for better accuracy
            search_query = obj.name_en
            if obj.road_name_en:
                search_query = f"{obj.name_en}, {obj.road_name_en}"

            nominatim_url = f"https://nominatim.openstreetmap.org/search?q={search_query}&format=json&limit=1"
            headers = {'User-Agent': 'BusRouteFinderApp/1.0 (your_email@example.com)'}  # Important for Nominatim

            try:
                response = requests.get(nominatim_url, headers=headers)
                response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
                data = response.json()

                if data:
                    obj.latitude = data[0]['lat']
                    obj.longitude = data[0]['lon']
                    self.message_user(request, f"Successfully geocoded '{search_query}'.")
                else:
                    self.message_user(request,
                                      f"Could not find coordinates for '{search_query}'. Please enter manually if needed.",
                                      level='warning')
            except requests.exceptions.RequestException as e:
                self.message_user(request, f"Error geocoding '{search_query}': {e}", level='error')
            except Exception as e:
                self.message_user(request, f"An unexpected error occurred during geocoding: {e}", level='error')

        super().save_model(request, obj, form, change)


@admin.register(BusLine)
class BusLineAdmin(admin.ModelAdmin):
    list_display = ('line_number', 'description')
    search_fields = ('line_number',)


@admin.register(RouteSegment)
class RouteSegmentAdmin(admin.ModelAdmin):
    # UPDATED: Removed distance and estimated time fields from list_display
    list_display = ('bus_line', 'bus_stop', 'order')
    list_filter = ('bus_line',)
    search_fields = ('bus_line__line_number', 'bus_stop__name_mm', 'bus_stop__name_en', 'bus_stop__road_name_mm',
                     'bus_stop__road_name_en')  # UPDATED: Added road names to search fields
    ordering = ('bus_line', 'order')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'preferred_language')
    search_fields = ('user__username', 'user__email', 'phone_number')
    list_filter = ('preferred_language',)


@admin.register(SavedRoute)
class SavedRouteAdmin(admin.ModelAdmin):
    list_display = ('user', 'start_stop', 'end_stop', 'name', 'created_at')
    list_filter = ('user', 'created_at')
    search_fields = ('user__username', 'start_stop__name_en', 'end_stop__name_en', 'name')
    ordering = ('-created_at',)