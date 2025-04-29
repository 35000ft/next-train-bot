import re
from typing import List, Optional

import httpx
from pydantic import BaseModel


class Cloud(BaseModel):
    cover: str
    base: Optional[int] = None


def wind_direction_to_text(degrees):
    """
    将风向角度转换为中文风向名称。

    参数:
        degrees (int): 风向角度（0° 到 360°）。

    返回:
        str: 中文风向名称。
    """
    directions = {
        (0, 22): "北风",
        (23, 67): "东北风",
        (68, 112): "东风",
        (113, 157): "东南风",
        (158, 202): "南风",
        (203, 247): "西南风",
        (248, 292): "西风",
        (293, 337): "西北风",
        (338, 360): "北风"
    }

    for (low, high), direction in directions.items():
        if low <= degrees <= high:
            return direction
    return "未知风向"


def parse_wind_speed(wind_str: str):
    """
    解析 METAR 报文中的风速信息。
    参数:
        wind_str (str): 风速字符串，格式如 '08013KT'。
    返回:
        dict: 包含风向（degrees）、风速（knots）、风速（km/h）、风速（m/s）和单位（raw_unit）的字典。
    """
    # 使用正则表达式提取风向和风速
    print(f'sd:{wind_str}')
    match = re.match(r"(\d{3})(\d{2})(KT|MPS)?", wind_str)
    if not match:
        raise ValueError(f"无法解析风速字符串: {wind_str}")

    # 获取风向和风速
    direction = int(match.group(1))
    speed = int(match.group(2))
    raw_unit = match.group(3) if match.group(3) else "KT"

    # 根据单位转换风速
    if raw_unit == "KT":
        speed_knots = speed
        speed_kmh = speed * 1.852
        speed_ms = speed * 0.514444
        unit = '节'
    elif raw_unit == "MPS":
        speed_kmh = speed * 3.6
        speed_ms = speed
        speed_knots = speed / 0.514444
        unit = '米每秒'
    else:
        raise ValueError(f"未知的风速单位: {raw_unit}")

    return {
        "raw_direction": direction,
        "direction": wind_direction_to_text(direction),
        "speed": speed,
        "speed_knots": speed_knots,
        "speed_kmh": speed_kmh,
        "speed_ms": speed_ms,
        "unit": unit
    }


class WeatherReport(BaseModel):
    metar_id: int
    icaoId: str
    receiptTime: str
    obsTime: int
    reportTime: str
    temp: int
    dewp: int
    wdir: int
    wspd: int
    wgst: Optional[int] = None
    visib: str
    altim: int
    slp: Optional[int] = None
    qcField: int
    wxString: Optional[str] = None
    presTend: Optional[str] = None
    maxT: Optional[int] = None
    minT: Optional[int] = None
    maxT24: Optional[int] = None
    minT24: Optional[int] = None
    precip: Optional[int] = None
    pcp3hr: Optional[int] = None
    pcp6hr: Optional[int] = None
    pcp24hr: Optional[int] = None
    snow: Optional[int] = None
    vertVis: Optional[int] = None
    metarType: str
    rawOb: str
    mostRecent: int
    lat: float
    lon: float
    elev: int
    prior: int
    name: str
    clouds: List[Cloud] = None
    rawTaf: str

    def __str__(self) -> str:
        wind_speed_obj: dict = parse_wind_speed(self.rawOb.split(' ')[2])

        # 拼接结果字符串
        return f"""
        机场: {self.name} (ICAO代码: {self.icaoId})
        报告时间: {self.reportTime} (UTC)
        接收时间: {self.receiptTime} (UTC)
        温度: {self.temp}°C, 露点: {self.dewp}°C
        风向: {wind_speed_obj.get("direction")} 风速: {wind_speed_obj.get('speed')} {wind_speed_obj.get('unit')}
        能见度: {self.visib}
        气压: {self.altim} hPa
        云层信息: {', '.join([f"{cloud.cover} {f'{cloud.base}ft' if cloud.base else ''}" for cloud in self.clouds])}

        METAR原始报告: {self.rawOb}
        TAF原始预报: {self.rawTaf}
        """


headers = {
    'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
}


async def get_airport_weather_report(icao_code: str) -> WeatherReport:
    url = 'https://aviationweather.gov/api/data/metar'
    params = {
        'ids': icao_code,
        "format": 'json',
        "taf": True
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        j_obj = resp.json()
        if len(j_obj) == 0:
            raise Exception(f'No such airport:{icao_code}')
        report: WeatherReport = WeatherReport(**j_obj[0])
        return report
