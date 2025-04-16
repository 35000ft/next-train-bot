from typing import List

from app.events.civil_aviation.Schemas import FlightInfo
from app.utils.exceptions import InputException

# 星空联盟成员航司代码
star_alliance = ["A3", "AC", "CA", "AI", "NZ", "NH", "OZ", "OS", "AV", "SN",
                 "CM", "OU", "MS", "ET", "BR", "LO", "LH", "ZH", "SQ", "SA",
                 "LX", "TP", "TG", "TK", "UA"]

# 天合联盟成员航司代码
skyteam_alliance = ["SU", "AR", "AM", "UX", "AF", "CI", "MU", "DL", "GA", "KQ",
                    "KL", "KE", "ME", "SV", "SK", "RO", "VN", "VS", "MF"]
# 寰宇一家成员航司代码
oneworld_alliance = ["AS", "AA", "BA", "CX", "FJ", "AY", "IB", "JL", "MH", "QF",
                     "QR", "AT", "RJ", "UL"]

民航一区 = ['CX', 'BA', 'QR', 'QF', 'AY', 'AF', 'SQ', 'EK', 'EY', 'DL']

# 海航
hna = ["HU", "GS", "8L", "JD", "PN", "UQ", "FU", "GX", "9H", "Y8", "GT", "HX", ]

alliance_map = {
    "oneworld": oneworld_alliance,
    "star_alliance": star_alliance,
    "skyteam": skyteam_alliance,
    "民航一区": 民航一区,
    "hna": hna,
}

alliance_name_map = {
    "skyteam": "skyteam",
    "sky": "skyteam",
    "st": "skyteam",
    "天合": "skyteam",
    "天合联盟": "skyteam",
    "鸟合": "skyteam",
    "oneworld": "oneworld",
    "ow": "oneworld",
    "一球": "oneworld",
    "寰宇一家": "oneworld",
    "星盟": "star_alliance",
    "星空联盟": "star_alliance",
    "星": "star_alliance",
    "star": "star_alliance",
    "star_alliance": "star_alliance",
    "sa": "star_alliance",
    "海航": "hna",
    "方威": "hna",
    "hna": "hna",
    # "民航一区": "no1_level",
    # "民航1区": "no1_level",
}


def map_airlines_alliance(airlines_code: str):
    if not airlines_code:
        return 'other'
    airlines_code = airlines_code.upper()
    if airlines_code in star_alliance:
        return 'star_alliance'
    elif airlines_code in skyteam_alliance:
        return 'skyteam'
    elif airlines_code in oneworld_alliance:
        return 'oneworld'
    elif airlines_code in hna:
        return 'hna'
    else:
        return 'other'


def filter_airport(flights: List[FlightInfo], is_dep: bool, target_airport: str):
    _result = []
    if is_dep:
        _result = filter(
            lambda x: target_airport in x.arr_airport or (
                    x.arr_airport_code and target_airport.upper() == x.arr_airport_code),
            list(_result))
    else:
        _result = filter(
            lambda x: target_airport in x.dep_airport or (
                    x.dep_airport_code and target_airport.upper() == x.dep_airport_code),
            list(_result))
    return _result


def filter_alliance(flights: List[FlightInfo], alliance_name: str) -> List[FlightInfo]:
    if not flights:
        return flights
    alliance_name = alliance_name_map.get(alliance_name)
    if not alliance_name:
        raise InputException(f'不支持的联盟: {alliance_name}')

    result = []
    for flight in flights:
        flight_no = flight.flight_no
        airlines_code = flight.airlines_code or (flight_no[0:2] if flight_no else None)
        airlines_alliance = map_airlines_alliance(airlines_code)
        if airlines_alliance == alliance_name:
            result.append(flight)
    return result


def filter_aircraft_model(flights: List[FlightInfo], aircraft_models: List[str]) -> List[FlightInfo]:
    if not aircraft_models:
        return flights
    return [x for x in flights
            if x.aircraft_model in aircraft_models]


def filter_airlines_by_code(flights: List[FlightInfo], airlines_codes: List[str]) -> List[FlightInfo]:
    if not airlines_codes:
        return flights
    return [x for x in flights if x.airlines_code or (x[0:2] if x else None) in airlines_codes]


def filter_airlines_by_name(flights: List[FlightInfo], airlines_name: str) -> List[FlightInfo]:
    if not airlines_name:
        return flights
    return [x for x in flights if x.airlines in airlines_name]


def filter_flight_no(flights: List[FlightInfo], flight_no: str) -> List[FlightInfo]:
    if not flight_no:
        return flights
    flight_no = flight_no.upper()
    return list(filter(lambda x: flight_no in x.flight_no, flights))


def flight_filter(flights: List[FlightInfo], **kwargs) -> List[FlightInfo]:
    flights = [x for x in flights if x is not None]
    if alliance_name := kwargs.get('alliance'):
        flights = filter_alliance(flights, alliance_name)
    if aircraft_model := kwargs.get('aircraft_models'):
        flights = filter_aircraft_model(flights, aircraft_model)
    if airlines_codes := kwargs.get('airlines_codes'):
        flights = filter_airlines_by_code(flights, airlines_codes)
    if airlines := kwargs.get('airlines'):
        flights = filter_airlines_by_name(flights, airlines)
    if flight_no := kwargs.get('flight_no'):
        flights = filter_flight_no(flights, flight_no)
    if target_airport := kwargs.get('dep_airport'):
        flights = filter_airport(flights, target_airport=target_airport, is_dep=True)
    if target_airport := kwargs.get('arr_airport'):
        flights = filter_airport(flights, target_airport=target_airport, is_dep=False)
    return flights
