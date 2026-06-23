"""In-memory grid index over the imported fuel stations, loaded once
per process. Used to find stations close to a route without external calls."""
import math
import threading
from collections import defaultdict

from routes.models import FuelStation

GRID_DEG = 0.5  # ~35 mile cells; station search radius is well under one cell

_lock = threading.Lock()
_grid = None
_stations = None


def _cell(lat, lon):
    return (int(lat // GRID_DEG), int(lon // GRID_DEG))


def _load():
    global _grid, _stations
    with _lock:
        if _grid is not None:
            return
        stations = list(
            FuelStation.objects.all().values(
                'id', 'opis_id', 'name', 'address', 'city', 'state',
                'retail_price', 'latitude', 'longitude',
            )
        )
        grid = defaultdict(list)
        for s in stations:
            grid[_cell(s['latitude'], s['longitude'])].append(s)
        _stations, _grid = stations, dict(grid)


def haversine_miles(lat1, lon1, lat2, lon2):
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = rlat2 - rlat1
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(a))


def stations_near_route(route_points, cumulative_miles, radius_miles):
    """Returns stations within radius_miles of the route, each annotated
    with route_mile (its position along the route)."""
    _load()

    # Sample roughly every 2 miles.
    sampled = []
    next_at = 0.0
    for pt, mile in zip(route_points, cumulative_miles):
        if mile >= next_at:
            sampled.append((pt, mile))
            next_at = mile + 2.0
    if sampled[-1][1] != cumulative_miles[-1]:
        sampled.append((route_points[-1], cumulative_miles[-1]))

    # bucket route samples by grid cell so each station only checks nearby ones
    samples_by_cell = defaultdict(list)
    for (lat, lon), mile in sampled:
        samples_by_cell[_cell(lat, lon)].append((lat, lon, mile))

    cells = set()
    for cell in samples_by_cell:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                cells.add((cell[0] + dr, cell[1] + dc))

    results = []
    seen = set()
    for cell in cells:
        for s in _grid.get(cell, ()):
            if s['id'] in seen:
                continue
            seen.add(s['id'])
            s_cell = _cell(s['latitude'], s['longitude'])
            best_dist, best_mile = None, None
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    for lat, lon, mile in samples_by_cell.get((s_cell[0] + dr, s_cell[1] + dc), ()):
                        d = haversine_miles(s['latitude'], s['longitude'], lat, lon)
                        if best_dist is None or d < best_dist:
                            best_dist, best_mile = d, mile
            if best_dist is not None and best_dist <= radius_miles:
                # Ignore stations with missing or non-positive prices which
                # would otherwise produce zero-cost results.
                price = s.get('retail_price')
                if price is None or price <= 0:
                    continue
                results.append({**s, 'route_mile': best_mile, 'detour_miles': round(best_dist, 1)})

    results.sort(key=lambda s: s['route_mile'])
    return results
