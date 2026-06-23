from django.db import models


class FuelStation(models.Model):
    opis_id = models.IntegerField()
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    rack_id = models.IntegerField()
    retail_price = models.FloatField()
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        indexes = [models.Index(fields=['latitude', 'longitude'])]
        constraints = [
            models.UniqueConstraint(
                fields=['opis_id', 'city', 'state'], name='unique_station_location'
            )
        ]

    def __str__(self):
        return f'{self.name} ({self.city}, {self.state}) ${self.retail_price:.3f}'
