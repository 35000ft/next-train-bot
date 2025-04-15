import asyncio
from datetime import datetime

from app.events.civil_aviation.CANFetcher import CANFetcher
from app.events.civil_aviation.HGHFetcher import HGHFetcher
from app.events.civil_aviation.SZXFetcher import SZXFetcher
from app.events.civil_aviation.Schemas import QueryFlightForm


async def main():
    fetcher = SZXFetcher()
    q_form = QueryFlightForm()
    flights = await fetcher.fetch_flights(_form=q_form, headless=True, )
    for x in flights:
        print(x.model_dump_json())


asyncio.run(main())
