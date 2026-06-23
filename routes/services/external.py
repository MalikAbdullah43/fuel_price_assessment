"""Wrappers around the two external APIs (Nominatim geocoding and OSRM
routing). Responses are cached so repeated queries don't hit them again."""
import hashlib

import polyline
import requests
from django.core.cache import cache

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
OSRM_URL = 'https://router.project-osrm.org/route/v1/driving'
USER_AGENT = 'fuel-route-assessment/1.0'

METERS_PER_MILE = 1609.344


class ExternalAPIError(Exception):
    """A free upstream API failed or returned no usable result."""


def _cached(key_parts, fetch):
    key = 'ext:' + hashlib.sha1('|'.join(key_parts).encode()).hexdigest()
    result = cache.get(key)
    if result is None:
        result = fetch()
        cache.set(key, result)
    return result


def geocode(place):
    """Resolve a free-text US location to (lat, lon, display_name)."""
    def fetch():
        resp = requests.get(
            NOMINATIM_URL,
            params={'q': place, 'countrycodes': 'us', 'format': 'json', 'limit': 1},
            headers={'User-Agent': USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()
        if not results:
            raise ExternalAPIError(f'Could not find a US location for "{place}".')
        hit = results[0]
        return float(hit['lat']), float(hit['lon']), hit['display_name']

    return _cached(['geocode', place.strip().lower()], fetch)


def fetch_route(start, finish):
    """One OSRM call: full route geometry and distance between two (lat, lon) points.

    Returns (points, total_miles) where points is a list of (lat, lon).
    """
    def fetch():
        coords = f'{start[1]},{start[0]};{finish[1]},{finish[0]}'
        resp = requests.get(
            f'{OSRM_URL}/{coords}',
            params={'overview': 'full', 'geometries': 'polyline'},
            headers={'User-Agent': USER_AGENT},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get('code') != 'Ok' or not data.get('routes'):
            raise ExternalAPIError('Routing service could not find a route.')
        route = data['routes'][0]
        return route['geometry'], route['distance'] / METERS_PER_MILE

    geometry, miles = _cached(
        ['route', f'{start[0]:.5f},{start[1]:.5f}', f'{finish[0]:.5f},{finish[1]:.5f}'],
        fetch,
    )
    return polyline.decode(geometry), miles
