import asyncio

from app.service.railsystem_service import get_station_by_keyword


def test_get_station_by_keyword(keyword):
    async def main():
        stations = await get_station_by_keyword(keyword)
        print('keyword:', keyword, 'stations:')
        if not stations:
            print('Not found')
            return
        if isinstance(stations, list):
            for station in stations:
                print(station.__dict__)
        else:
            print(stations.__dict__)

    asyncio.run(main())


if __name__ == '__main__':
    test_get_station_by_keyword('JRX')
