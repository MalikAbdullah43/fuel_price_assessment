"""Picks the cheapest set of fuel stops along a route.

Greedy strategy: at every station, if a cheaper station is reachable
within a full tank, buy just enough fuel to get there; otherwise fill
the tank. The vehicle is assumed to start with a full tank (see README).
"""


class RouteNotDrivableError(Exception):
    """A gap between usable fuel stations exceeds the vehicle's range."""


def plan_fuel_stops(stations, total_miles, range_miles, mpg):
    """stations: list of dicts with 'route_mile' and 'retail_price',
    sorted by route_mile. Returns (stops, total_cost).
    """
    # Destination acts as a free "station": the greedy will always buy
    # only what is needed to reach it.
    points = [s for s in stations if 0 < s['route_mile'] < total_miles]
    points.append({'route_mile': total_miles, 'retail_price': 0.0, '_destination': True})

    fuel_miles = float(range_miles)
    position = 0.0
    stops = []
    total_cost = 0.0

    for i, here in enumerate(points):
        leg = here['route_mile'] - position
        fuel_miles -= leg
        position = here['route_mile']
        if fuel_miles < 0:
            raise RouteNotDrivableError(
                f'No fuel station within {range_miles} miles around '
                f'mile {position:.0f} of the route.'
            )
        if here.get('_destination'):
            break

        # Find the first station cheaper than this one within a full tank.
        target = None
        for nxt in points[i + 1:]:
            if nxt['route_mile'] - position > range_miles:
                break
            if nxt['retail_price'] < here['retail_price']:
                target = nxt
                break

        if target is not None:
            need_miles = target['route_mile'] - position
            buy_miles = max(0.0, need_miles - fuel_miles)
        else:
            buy_miles = range_miles - fuel_miles

        if buy_miles > 1e-9:
            gallons = buy_miles / mpg
            cost = gallons * here['retail_price']
            total_cost += cost
            fuel_miles += buy_miles
            stops.append({
                **{k: v for k, v in here.items() if not k.startswith('_')},
                'gallons': round(gallons, 2),
                'fuel_cost': round(cost, 2),
            })

    return stops, round(total_cost, 2)
