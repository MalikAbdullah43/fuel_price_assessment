from django.test import SimpleTestCase

from routes.services.planner import RouteNotDrivableError, plan_fuel_stops


def station(mile, price, name='S'):
    return {'route_mile': mile, 'retail_price': price, 'name': f'{name}@{mile}'}


class PlannerTests(SimpleTestCase):
    RANGE = 500
    MPG = 10

    def plan(self, stations, total):
        return plan_fuel_stops(stations, total, self.RANGE, self.MPG)

    def test_no_stops_when_destination_within_range(self):
        stops, cost = self.plan([station(100, 3.0)], 400)
        self.assertEqual(stops, [])
        self.assertEqual(cost, 0.0)

    def test_single_fill_buys_only_whats_needed(self):
        # 600 mile trip, one station at mile 300: need 100 more miles of
        # fuel (10 gal) to cover the 300 remaining after arriving with 200.
        stops, cost = self.plan([station(300, 3.0)], 600)
        self.assertEqual(len(stops), 1)
        self.assertEqual(stops[0]['gallons'], 10.0)
        self.assertEqual(cost, 30.0)

    def test_buys_minimum_at_expensive_station_to_reach_cheap_one(self):
        # Arrive at the pricey stop with 50 miles of fuel; buy just the
        # 200 miles (20 gal) needed to reach the cheap one, finish cheap.
        stations = [station(450, 4.0, 'pricey'), station(700, 2.0, 'cheap')]
        stops, cost = self.plan(stations, 800)
        self.assertEqual([s['gallons'] for s in stops], [20.0, 10.0])
        self.assertEqual(cost, 20 * 4.0 + 10 * 2.0)

    def test_skips_pricey_station_when_cheap_fill_reaches_destination(self):
        # The destination is exactly one tank from the cheap stop, so the
        # optimal plan never buys at the pricey one.
        stations = [station(400, 2.0, 'cheap'), station(850, 4.0, 'pricey')]
        stops, cost = self.plan(stations, 900)
        self.assertEqual([s['gallons'] for s in stops], [40.0])
        self.assertEqual(cost, 40 * 2.0)

    def test_fills_up_at_cheap_station_when_next_ones_cost_more(self):
        # Destination is beyond one tank from the cheap stop: fill there,
        # then top up the small remainder at the pricey one.
        stations = [station(400, 2.0, 'cheap'), station(850, 4.0, 'pricey')]
        stops, cost = self.plan(stations, 960)
        self.assertEqual([s['gallons'] for s in stops], [40.0, 6.0])
        self.assertEqual(cost, 40 * 2.0 + 6 * 4.0)

    def test_unreachable_gap_raises(self):
        with self.assertRaises(RouteNotDrivableError):
            self.plan([station(100, 3.0)], 700)  # 600 mile gap after mile 100

    def test_stations_beyond_destination_ignored(self):
        stops, cost = self.plan([station(450, 9.9), station(950, 1.0)], 480)
        self.assertEqual(stops, [])
        self.assertEqual(cost, 0.0)
