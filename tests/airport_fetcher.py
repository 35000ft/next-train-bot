import asyncio

from app.events.civil_aviation.Schemas import QueryFlightForm
from app.events.civil_aviation.ShanghaiFetcher import PVGFetcher


async def main():
    fetcher = PVGFetcher()
    q_form = QueryFlightForm(airport='广州')
    flights = await fetcher.fetch_flights(_form=q_form, headless=True)
    print()


asyncio.run(main())
