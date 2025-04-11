import asyncio
from datetime import datetime

from app.events.civil_aviation.HGHFetcher import HGHFetcher
from app.events.civil_aviation.Schemas import QueryFlightForm


async def main():
    fetcher = HGHFetcher()
    q_form = QueryFlightForm()
    flights = await fetcher.fetch_flights(_form=q_form, headless=True, arr=True)
    print()


asyncio.run(main())
