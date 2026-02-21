from sqlalchemy import Column, Integer, String, Text, Date, Float, DateTime, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class BusinessUnit(Base):
    __tablename__ = "business_units"

    id = Column(Integer, primary_key=True)
    office_name = Column(String(100), unique=True, nullable=False)
    address = Column(Text)
    latitude = Column(Float)
    longitude = Column(Float)

    managers = relationship("Manager", back_populates="business_unit")


class Manager(Base):
    __tablename__ = "managers"

    id = Column(Integer, primary_key=True)
    full_name = Column(String(200), nullable=False)
    position = Column(String(100))          # Специалист | Ведущий специалист | Главный специалист
    office = Column(String(100), ForeignKey("business_units.office_name"))
    skills = Column(ARRAY(String))          # ['VIP', 'ENG', 'KZ']
    current_load = Column(Integer, default=0)

    business_unit = relationship("BusinessUnit", back_populates="managers")
    assignments = relationship("Assignment", back_populates="manager")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True)
    guid = Column(UUID(as_uuid=False), unique=True, nullable=False)
    gender = Column(String(20))
    birth_date = Column(Date)
    description = Column(Text)
    attachment = Column(String(255))
    segment = Column(String(20))            # Mass | VIP | Priority
    country = Column(String(100))
    region = Column(String(100))
    city = Column(String(100))
    street = Column(String(200))
    house = Column(String(20))

    analysis = relationship("TicketAnalysis", back_populates="ticket", uselist=False)
    assignment = relationship("Assignment", back_populates="ticket", uselist=False)


class TicketAnalysis(Base):
    __tablename__ = "ticket_analysis"

    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), unique=True)
    ticket_type = Column(String(100))       # Жалоба | Смена данных | ...
    sentiment = Column(String(20))          # Позитивный | Нейтральный | Негативный
    priority_score = Column(Integer)        # 1-10
    language = Column(String(5))            # RU | KZ | ENG
    summary = Column(Text)
    recommendation = Column(Text)
    client_lat = Column(Float)
    client_lon = Column(Float)
    nearest_office = Column(String(100))
    attachment_description = Column(Text)   # Vision analysis of the image, or missing-attachment note
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())

    ticket = relationship("Ticket", back_populates="analysis")


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), unique=True)
    manager_id = Column(Integer, ForeignKey("managers.id"))
    assigned_office = Column(String(100))
    round_robin_index = Column(Integer)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())

    ticket = relationship("Ticket", back_populates="assignment")
    manager = relationship("Manager", back_populates="assignments")
