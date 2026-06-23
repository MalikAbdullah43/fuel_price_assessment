from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import render
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .services.external import ExternalAPIError, fetch_route, geocode
from .services.planner import RouteNotDrivableError, plan_fuel_stops
from .services.stations import haversine_miles, stations_near_route


def _simplify(points, cumulative, spacing_miles=0.5):
    """Thin the route geometry to ~one point per spacing_miles for the
    JSON response; full resolution is only needed server-side."""
    out = []
    next_at = 0.0
    for (lat, lng), mile in zip(points, cumulative):
        if mile >= next_at:
            out.append([round(lat, 5), round(lng, 5)])
            next_at = mile + spacing_miles
    last = [round(points[-1][0], 5), round(points[-1][1], 5)]
    if out[-1] != last:
        out.append(last)
    return out


class RoutePlanView(APIView):
    """GET /api/route/?start=<US location>&finish=<US location>

    Returns the driving route, cost-optimal fuel stops and total fuel cost.
    """

    def get(self, request):
        start_q = request.query_params.get('start', '').strip()
        finish_q = request.query_params.get('finish', '').strip()
        if not start_q or not finish_q:
            return Response(
                {'error': 'Both "start" and "finish" query parameters are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            start = geocode(start_q)
            finish = geocode(finish_q)
            points, total_miles = fetch_route(start[:2], finish[:2])
        except ExternalAPIError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        # Cumulative miles along the decoded geometry.
        cumulative = [0.0]
        for (lat1, lon1), (lat2, lon2) in zip(points, points[1:]):
            cumulative.append(cumulative[-1] + haversine_miles(lat1, lon1, lat2, lon2))

        nearby = stations_near_route(
            points, cumulative, settings.STATION_SEARCH_RADIUS_MILES
        )

        try:
            stops, total_cost = plan_fuel_stops(
                nearby, total_miles, settings.VEHICLE_RANGE_MILES, settings.VEHICLE_MPG
            )
        except RouteNotDrivableError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        fuel_stops = [
            {
                'name': s['name'],
                'address': s['address'],
                'city': s['city'],
                'state': s['state'],
                'price_per_gallon': round(s['retail_price'], 3),
                'gallons_purchased': s['gallons'],
                'fuel_cost': s['fuel_cost'],
                'miles_from_start': round(s['route_mile'], 1),
                'location': {'lat': s['latitude'], 'lng': s['longitude']},
            }
            for s in stops
        ]

        map_query = urlencode({'start': start_q, 'finish': finish_q})
        return Response({
            'start': {'query': start_q, 'resolved': start[2],
                      'location': {'lat': start[0], 'lng': start[1]}},
            'finish': {'query': finish_q, 'resolved': finish[2],
                       'location': {'lat': finish[0], 'lng': finish[1]}},
            'route': {
                'total_distance_miles': round(total_miles, 1),
                'geometry': _simplify(points, cumulative),
            },
            'vehicle': {
                'range_miles': settings.VEHICLE_RANGE_MILES,
                'mpg': settings.VEHICLE_MPG,
            },
            'fuel_stops': fuel_stops,
            'total_fuel_cost': total_cost,
            'total_gallons_purchased': round(sum(s['gallons'] for s in stops), 2),
            'map_url': request.build_absolute_uri(f'/map/?{map_query}'),
        })


def map_view(request):
    """Interactive Leaflet map of the route and its fuel stops."""
    return render(request, 'map.html', {
        'start': request.GET.get('start', ''),
        'finish': request.GET.get('finish', ''),
    })
