"""Imports the fuel price CSV into the database. Coordinates come from
data/city_coords.json (city centroids built offline from GeoNames), so
no geocoding happens here or at request time."""
import csv
import json

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from routes.models import FuelStation


class Command(BaseCommand):
    help = 'Import fuel stations from the assessment CSV with offline-geocoded coordinates.'

    def handle(self, *args, **options):
        csv_path = settings.DATA_DIR / 'fuel-prices-for-be-assessment.csv'
        coords_path = settings.DATA_DIR / 'city_coords.json'

        with open(coords_path) as f:
            city_coords = json.load(f)

        # Dedupe: the CSV repeats stations under slightly different names.
        # Keep the cheapest price seen for each (opis_id, city, state).
        stations = {}
        skipped = 0
        with open(csv_path, newline='') as f:
            for row in csv.DictReader(f):
                city = row['City'].strip()
                state = row['State'].strip().upper()
                coords = city_coords.get(f'{city.lower()}|{state}')
                if coords is None:
                    skipped += 1
                    continue
                key = (int(row['OPIS Truckstop ID']), city.lower(), state)
                price = float(row['Retail Price'])
                if key in stations and stations[key].retail_price <= price:
                    continue
                stations[key] = FuelStation(
                    opis_id=key[0],
                    name=row['Truckstop Name'].strip(),
                    address=row['Address'].strip(),
                    city=city,
                    state=state,
                    rack_id=int(row['Rack ID']),
                    retail_price=price,
                    latitude=coords[0],
                    longitude=coords[1],
                )

        with transaction.atomic():
            FuelStation.objects.all().delete()
            FuelStation.objects.bulk_create(stations.values(), batch_size=1000)

        self.stdout.write(self.style.SUCCESS(
            f'Imported {len(stations)} stations '
            f'({skipped} rows skipped: no US coordinates available).'
        ))
