from typing import List

from app.events.civil_aviation.Schemas import FlightInfo


class BaseFlightFetcher:
    def filter_flights(self, flights: List[FlightInfo], **kwargs):
        pass
