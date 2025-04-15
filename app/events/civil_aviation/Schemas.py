from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class QueryFlightForm(BaseModel):
    flight_no: Optional[str] = None
    airlines: Optional[str] = None
    airport: Optional[str] = None
    at_time: Optional[datetime] = None
    aircraft_models: List[str] = []
    airlines_codes: List[str] = []
    alliance: Optional[str] = None


class FlightInfo(BaseModel):
    flight_no: str
    shared_codes: List[str]
    airlines: Optional[str] = None
    airlines_code: Optional[str] = None
    dep_airport: str
    dep_airport_code: Optional[str] = None
    arr_airport: str
    arr_airport_code: Optional[str] = None
    via_airports: List[str] = []
    dep_time: Optional[str] = None
    arr_time: Optional[str] = None
    act_dep_time: Optional[str] = None
    act_arr_time: Optional[str] = None
    date: datetime
    terminal: Optional[str] = None
    gate: Optional[str] = None
    status: Optional[str] = None
    carousel: Optional[str] = None
    aircraft_model: Optional[str] = None
    stand: Optional[str] = None
    airlines_alliance: Optional[str] = None

    def is_after(self, _date: datetime, is_dep: bool) -> bool:
        flight_datetime = self.get_time(is_dep)
        if not flight_datetime:
            return False

        return flight_datetime > _date

    def get_time(self, is_dep) -> Optional[datetime]:
        time_str = self.dep_time if is_dep else self.arr_time
        if not time_str:
            return
        try:
            time_obj = datetime.strptime(time_str, '%H:%M').time()
        except ValueError:
            return
        flight_datetime = datetime.combine(self.date, time_obj)
        return flight_datetime
