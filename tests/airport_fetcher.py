import asyncio

from app.events.civil_aviation.Schemas import QueryFlightForm
from app.events.civil_aviation.ShanghaiFetcher import PVGFetcher


async def main():
    fetcher = PVGFetcher()
    q_form = QueryFlightForm()
    flights = await fetcher.fetch_flights(_form=q_form, headless=True, )
    for x in flights:
        print(x.model_dump_json())


asyncio.run(main())
