# Fuel Route Planner

Django API that takes a start and finish location in the USA and returns the
driving route, the cheapest places to fuel up along the way, and the total
fuel cost. Vehicle is assumed to have a 500 mile range and do 10 MPG.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py import_stations
python manage.py runserver
```

`import_stations` loads the fuel price CSV into sqlite. It only needs to run
once.

## Usage

```
GET /api/route/?start=New York, NY&finish=Los Angeles, CA
```

Response contains the route geometry, total distance, the list of fuel stops
(station, price, gallons bought, cost, mile marker) and the total fuel cost:

```json
{
  "route": {"total_distance_miles": 2798.2, "geometry": [[40.71, -74.0], ...]},
  "fuel_stops": [
    {
      "name": "AKAL TRAVEL CENTER",
      "city": "Waco",
      "state": "NE",
      "price_per_gallon": 2.799,
      "gallons_purchased": 50.0,
      "fuel_cost": 139.95,
      "miles_from_start": 1337.2
    }
  ],
  "total_fuel_cost": 694.68,
  "map_url": "http://localhost:8000/map/?start=...&finish=..."
}
```

Open `map_url` in a browser to see the route and the stops on a map (Leaflet
+ OpenStreetMap tiles). There's also a postman_collection.json with example
requests.

## How it works

Geocoding of start/finish goes through Nominatim and routing through the
OSRM demo server, both free. Only one routing call is made per route, and
both responses are cached, so repeating a request hits no external API at
all.

The CSV has no coordinates for the stations, so I geocoded them offline
against the GeoNames place dataset (city centroids) and shipped the result
as data/city_coords.json. At runtime the stations live in an in-memory grid
index and finding the ones near the route is just local math, no API calls.

Stop selection uses the standard greedy strategy for the fixed-tank fuel
problem: at each station, if there's a cheaper station reachable within a
full tank, buy just enough fuel to get there, otherwise fill up. This
minimizes total spend, which is why the output sometimes has small top-ups
at expensive stations right before a cheap one.

## Assumptions

- The truck starts with a full tank, so trips under 500 miles need no stops
  and cost $0.
- Stations are placed at their city centroid since the CSV has no street
  coordinates. The search corridor around the route is 7.5 miles to absorb
  that imprecision.
- The CSV repeats some stations with different names; duplicates keep the
  cheapest price.
- About 8% of rows are dropped during import (Canadian locations and a few
  towns GeoNames doesn't know). 6589 stations remain, which is plenty of
  coverage for US routes.

## Tests

```bash
python manage.py test routes
```

Covers the refueling algorithm: just-enough vs fill-up decisions, skipping
expensive stations, and unreachable gaps.
