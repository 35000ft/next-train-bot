import asyncio
from pathlib import Path

from app.service.realtime_service import get_schedule_image_by_html2image


def test_gen_schedule_image():
    station_id, line_id = '13', '1'
    asyncio.run(
        get_schedule_image_by_html2image(station_id, line_id, output_dir=Path('data/temp'), filename='新街口1号线.png'))


if __name__ == '__main__':
    test_gen_schedule_image()
