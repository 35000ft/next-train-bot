import asyncio
from datetime import datetime

from app.events.civil_aviation.CANFetcher import CANFetcher
from app.events.civil_aviation.HGHFetcher import HGHFetcher
from app.events.civil_aviation.Schemas import QueryFlightForm


async def main():
    fetcher = CANFetcher()
    q_form = QueryFlightForm(alliance='星空联盟')
    flights = await fetcher.fetch_flights(_form=q_form, headless=True, )
    print()


asyncio.run(main())
