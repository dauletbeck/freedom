import os
import threading
from typing import List, Optional
from collections import defaultdict

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, text

from database import get_db, init_db
from models import Ticket, TicketAnalysis, Manager, BusinessUnit, Assignment
from schemas import (
    TicketOut,
    ManagerOut,
    BusinessUnitOut,
    StatsOut,
    AssistantRequest,
    AssistantResponse,
)
from llm import run_assistant_query
from routing import filter_managers, has_explicit_foreign_location, EQUIDISTANT_THRESHOLD_KM

app = FastAPI(title="FIRE — Freedom Intelligent Routing Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pipeline state
_pipeline_status = {"running": False, "progress": 0, "total": 0, "current": "", "done": False, "error": None}


def _build_cross_city_consultation_note(ticket: Ticket, managers: List[Manager]) -> Optional[str]:
    """Build a non-blocking UI note for explicit abroad mentions in ticket text."""
    if not ticket.description or not has_explicit_foreign_location(ticket.description):
        return None
    if not ticket.analysis or not ticket.assignment:
        return None
    if ticket.analysis.ticket_type == "Спам":
        return None

    eligible_global = filter_managers(
        managers=managers,
        office=None,
        segment=ticket.segment or "Mass",
        ticket_type=ticket.analysis.ticket_type or "Консультация",
        language=ticket.analysis.language or "RU",
        sentiment=ticket.analysis.sentiment or "Нейтральный",
        limit=None,
    )
    assigned_office = ticket.assignment.assigned_office
    alternative = next(
        (m for m in eligible_global if m.office and m.office != assigned_office),
        None,
    )
    if not alternative:
        return None

    return (
        "Клиент явно указал, что находится за пределами Казахстана. "
        "По правилу организаторов распределение сохраняется 50/50 между Астаной и Алматы. "
        f"Для онлайн-консультации можно рассмотреть {alternative.full_name} "
        f"({alternative.office}, текущая нагрузка {alternative.current_load})."
    )


def _build_skill_gap_routing_note(ticket: Ticket) -> Optional[str]:
    """
    Build a note when a client was routed to a non-nearest office because the
    nearest office had no managers with the required skills (VIP, KZ, ENG, etc.).

    Uses pre-computed distances stored in ticket_analysis (geo_nearest_office,
    dist_to_nearest_km, dist_to_assigned_km) to avoid re-running Haversine at
    query time.
    """
    if not ticket.analysis or not ticket.assignment:
        return None
    if ticket.analysis.ticket_type == "Спам":
        return None

    geo_nearest = ticket.analysis.geo_nearest_office
    assigned_office = ticket.assignment.assigned_office
    dist_nearest = ticket.analysis.dist_to_nearest_km
    dist_assigned = ticket.analysis.dist_to_assigned_km

    if not geo_nearest or not assigned_office:
        return None
    if geo_nearest == assigned_office:
        return None  # no fallback — normal routing
    if dist_nearest is None or dist_assigned is None:
        return None
    if dist_assigned - dist_nearest <= EQUIDISTANT_THRESHOLD_KM:
        return None  # within tie-break threshold — not a skill-gap fallback

    # Infer reason from the ticket's constraints
    segment = ticket.segment or "Mass"
    ticket_type = ticket.analysis.ticket_type or "Консультация"
    language = ticket.analysis.language or "RU"

    if segment in ("VIP", "Priority"):
        reason = f"в офисе {geo_nearest} нет менеджеров с навыком VIP"
    elif ticket_type == "Смена данных":
        reason = f"в офисе {geo_nearest} нет Главного специалиста"
    elif language == "KZ":
        reason = f"в офисе {geo_nearest} нет менеджеров с навыком KZ"
    elif language == "ENG":
        reason = f"в офисе {geo_nearest} нет менеджеров с навыком ENG"
    else:
        reason = f"в офисе {geo_nearest} нет подходящих менеджеров"

    return (
        f"Клиент направлен в {assigned_office} ({dist_assigned:.0f} км), "
        f"хотя ближайший офис — {geo_nearest} ({dist_nearest:.0f} км). "
        f"Причина: {reason}. "
        f"Рекомендуется рассмотреть назначение менеджера из офиса {geo_nearest} в стандартном режиме."
    )


def _serialize_ticket(ticket: Ticket, managers: List[Manager]) -> TicketOut:
    base = TicketOut.model_validate(ticket)
    cross_city_note = _build_cross_city_consultation_note(ticket, managers)
    skill_gap_note = _build_skill_gap_routing_note(ticket)
    return base.model_copy(update={
        "cross_city_consultation_note": cross_city_note,
        "skill_gap_routing_note": skill_gap_note,
    })


@app.on_event("startup")
def on_startup():
    init_db()


# ── Pipeline ──────────────────────────────────────────────────────────────────

@app.post("/api/pipeline/run")
def run_pipeline_endpoint(background_tasks: BackgroundTasks):
    if _pipeline_status["running"]:
        return {"message": "Pipeline already running", "status": _pipeline_status}

    def _run():
        from pipeline import run_pipeline
        _pipeline_status.update({"running": True, "done": False, "error": None, "progress": 0})

        def cb(i, total, guid):
            _pipeline_status["progress"] = i
            _pipeline_status["total"] = total
            _pipeline_status["current"] = guid

        try:
            run_pipeline(progress_callback=cb)
            _pipeline_status["done"] = True
        except Exception as e:
            _pipeline_status["error"] = str(e)
        finally:
            _pipeline_status["running"] = False

    background_tasks.add_task(_run)
    return {"message": "Pipeline started", "status": _pipeline_status}


@app.get("/api/pipeline/status")
def pipeline_status():
    return _pipeline_status


@app.post("/api/pipeline/reset")
def reset_pipeline(db: Session = Depends(get_db)):
    """Wipe all processed data so the pipeline can be rerun from scratch."""
    if _pipeline_status["running"]:
        raise HTTPException(status_code=409, detail="Pipeline is currently running — stop it first")

    # Delete in FK-safe order
    db.query(Assignment).delete()
    db.query(TicketAnalysis).delete()
    db.query(Ticket).delete()
    db.query(Manager).delete()
    db.query(BusinessUnit).delete()
    db.commit()

    _pipeline_status.update({"running": False, "progress": 0, "total": 0, "current": "", "done": False, "error": None})
    return {"message": "Database reset — ready for a fresh pipeline run"}


# ── Tickets ───────────────────────────────────────────────────────────────────

@app.get("/api/tickets", response_model=List[TicketOut])
def list_tickets(
    skip: int = 0,
    limit: int = 100,
    segment: Optional[str] = None,
    ticket_type: Optional[str] = None,
    language: Optional[str] = None,
    office: Optional[str] = None,
    manager_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Ticket).options(
        joinedload(Ticket.analysis),
        joinedload(Ticket.assignment).joinedload(Assignment.manager),
    )
    if segment:
        q = q.filter(Ticket.segment == segment)
    if ticket_type:
        q = q.join(TicketAnalysis).filter(TicketAnalysis.ticket_type == ticket_type)
    if language:
        q = q.join(TicketAnalysis).filter(TicketAnalysis.language == language)
    if office:
        q = q.join(Assignment).filter(Assignment.assigned_office == office)
    if manager_id:
        q = q.join(Assignment).filter(Assignment.manager_id == manager_id)

    tickets = q.offset(skip).limit(limit).all()
    managers = db.query(Manager).all()
    return [_serialize_ticket(ticket, managers) for ticket in tickets]


@app.get("/api/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = (
        db.query(Ticket)
        .options(
            joinedload(Ticket.analysis),
            joinedload(Ticket.assignment).joinedload(Assignment.manager),
        )
        .filter(Ticket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    managers = db.query(Manager).all()
    return _serialize_ticket(ticket, managers)


# ── Managers ──────────────────────────────────────────────────────────────────

@app.get("/api/managers")
def list_managers(office: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(Manager)
    if office:
        q = q.filter(Manager.office == office)
    managers = q.order_by(Manager.office, Manager.current_load).all()

    assigned_counts = dict(
        db.query(Assignment.manager_id, func.count(Assignment.id))
        .group_by(Assignment.manager_id)
        .all()
    )
    return [
        {
            "id": m.id,
            "full_name": m.full_name,
            "position": m.position,
            "office": m.office,
            "skills": m.skills or [],
            "current_load": m.current_load,
            "assigned_count": assigned_counts.get(m.id, 0),
            "prior_load": m.current_load - assigned_counts.get(m.id, 0),
        }
        for m in managers
    ]


# ── Business Units ────────────────────────────────────────────────────────────

@app.get("/api/business-units", response_model=List[BusinessUnitOut])
def list_business_units(db: Session = Depends(get_db)):
    return db.query(BusinessUnit).all()


# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(Ticket).count()

    by_type = {
        str(r[0] or "N/A"): r[1]
        for r in db.query(TicketAnalysis.ticket_type, func.count()).group_by(TicketAnalysis.ticket_type).all()
    }
    by_sentiment = {
        str(r[0] or "N/A"): r[1]
        for r in db.query(TicketAnalysis.sentiment, func.count()).group_by(TicketAnalysis.sentiment).all()
    }
    by_language = {
        str(r[0] or "N/A"): r[1]
        for r in db.query(TicketAnalysis.language, func.count()).group_by(TicketAnalysis.language).all()
    }
    by_segment = {
        str(r[0] or "N/A"): r[1]
        for r in db.query(Ticket.segment, func.count()).group_by(Ticket.segment).all()
    }
    by_office = {
        str(r[0] or "N/A"): r[1]
        for r in db.query(Assignment.assigned_office, func.count()).group_by(Assignment.assigned_office).all()
    }

    avg_priority_row = db.query(func.avg(TicketAnalysis.priority_score)).scalar()
    avg_priority = round(float(avg_priority_row or 0), 2)

    # Manager loads — split into prior (from CSV) and assigned (this pipeline run)
    assigned_counts = dict(
        db.query(Assignment.manager_id, func.count(Assignment.id))
        .group_by(Assignment.manager_id)
        .all()
    )
    managers = db.query(Manager).order_by(Manager.current_load.desc()).all()
    manager_loads = [
        {
            "id": m.id,
            "name": m.full_name,
            "office": m.office,
            "position": m.position,
            "skills": m.skills or [],
            "load": m.current_load,
            "assigned_count": assigned_counts.get(m.id, 0),
            "prior_load": m.current_load - assigned_counts.get(m.id, 0),
        }
        for m in managers
    ]

    return {
        "total_tickets": total,
        "by_type": by_type,
        "by_sentiment": by_sentiment,
        "by_language": by_language,
        "by_segment": by_segment,
        "by_office": by_office,
        "avg_priority": avg_priority,
        "manager_loads": manager_loads,
    }


# ── AI Assistant (Star Task) ──────────────────────────────────────────────────

@app.post("/api/assistant")
def assistant_query(req: AssistantRequest, db: Session = Depends(get_db)):
    # Build a brief context summary for the LLM
    total = db.query(Ticket).count()
    by_type = {
        str(r[0] or "N/A"): r[1]
        for r in db.query(TicketAnalysis.ticket_type, func.count()).group_by(TicketAnalysis.ticket_type).all()
    }
    by_office = {
        str(r[0] or "N/A"): r[1]
        for r in db.query(Assignment.assigned_office, func.count()).group_by(Assignment.assigned_office).all()
    }
    db_context = f"Total tickets: {total}\nBy type: {by_type}\nBy office: {by_office}"

    result = run_assistant_query(req.query, db_context)

    # If SQL provided, execute it safely and return rows
    chart_data = None
    if result.get("sql"):
        try:
            rows = db.execute(text(result["sql"])).fetchall()
            keys = db.execute(text(result["sql"])).keys()
            chart_data = {
                "labels": [str(r[0]) for r in rows],
                "values": [r[1] if len(r) > 1 else 1 for r in rows],
                "title": result.get("chart_title", ""),
            }
        except Exception as e:
            chart_data = None
            result["answer"] += f"\n\n(SQL error: {e})"

    return AssistantResponse(
        answer=result.get("answer", ""),
        chart_type=result.get("chart_type"),
        chart_data=chart_data,
        sql=result.get("sql"),
    )
