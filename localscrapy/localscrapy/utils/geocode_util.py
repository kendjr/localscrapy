import json
import time
import os
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

# Define the cache file path relative to the project root
CACHE_FILE = os.path.join(os.path.dirname(__file__), '..', 'geocode_cache.json')

def load_cache():
    """Load the geocoding cache from a JSON file."""
    try:
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_cache(cache):
    """Save the geocoding cache to a JSON file."""
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)

def get_geocode(location_str):
    """
    Convert a location string to geographic coordinates using Nominatim.
    Returns a dict {'latitude': float, 'longitude': float} or None if geocoding fails.
    """
    if not location_str:  # Handle None or empty string inputs
        return None

    cache = load_cache()
    if location_str in cache:
        return cache[location_str]

    geolocator = Nominatim(user_agent="event_scraper")
    try:
        location = geolocator.geocode(location_str)
        if location:
            coordinates = {'latitude': location.latitude, 'longitude': location.longitude}
            cache[location_str] = coordinates
            save_cache(cache)
            time.sleep(1)  # Respect Nominatim's 1 request/second limit
            return coordinates
        else:
            print(f"Could not geocode location: {location_str}")
            return None
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"Geocoding error for {location_str}: {e}")
        return None