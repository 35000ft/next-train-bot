from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class QueryFlightForm(BaseModel):
    flight_no: Optional[str] = None
    airlines: Optional[str] = None
    airport: Optional[str] = None
    at_time: Optional[datetime] = None
    aircraft_models: List[str] = []


class FlightInfo(BaseModel):
    flight_no: str
    shared_codes: List[str]
    airlines: Optional[str] = None
    dep_airport: str
    arr_airport: str
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
