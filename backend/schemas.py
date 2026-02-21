from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


class BusinessUnitOut(BaseModel):
    id: int
    office_name: str
    address: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]

    class Config:
        from_attributes = True


class ManagerOut(BaseModel):
    id: int
    full_name: str
    position: Optional[str]
    office: Optional[str]
    skills: Optional[List[str]]
    current_load: int

    class Config:
        from_attributes = True


class TicketAnalysisOut(BaseModel):
    ticket_type: Optional[str]
    sentiment: Optional[str]
    priority_score: Optional[int]
    language: Optional[str]
    summary: Optional[str]
    recommendation: Optional[str]
    attachment_description: Optional[str]
    client_lat: Optional[float]
    client_lon: Optional[float]
    nearest_office: Optional[str]
    analyzed_at: Optional[datetime]

    class Config:
        from_attributes = True


class AssignmentOut(BaseModel):
    assigned_office: Optional[str]
    round_robin_index: Optional[int]
    assigned_at: Optional[datetime]
    manager: Optional[ManagerOut]

    class Config:
        from_attributes = True


class TicketOut(BaseModel):
    id: int
    guid: str
    gender: Optional[str]
    birth_date: Optional[date]
    description: Optional[str]
    attachment: Optional[str]
    segment: Optional[str]
    country: Optional[str]
    region: Optional[str]
    city: Optional[str]
    street: Optional[str]
    house: Optional[str]
    analysis: Optional[TicketAnalysisOut]
    assignment: Optional[AssignmentOut]

    class Config:
        from_attributes = True


class StatsOut(BaseModel):
    total_tickets: int
    by_type: dict
    by_sentiment: dict
    by_segment: dict
    by_language: dict
    by_office: dict
    avg_priority: float
    manager_loads: List[dict]


class AssistantRequest(BaseModel):
    query: str


class AssistantResponse(BaseModel):
    answer: str
    chart_type: Optional[str]
    chart_data: Optional[dict]
    sql: Optional[str]
