"""
Main data processing pipeline:
1. Load CSVs into PostgreSQL
2. Run LLM analysis on each ticket
3. Apply routing rules and assign managers
"""

import os
import csv
import uuid
import math
from datetime import datetime
from typing import Optional
from time import perf_counter

import pandas as pd
from sqlalchemy.orm import Session

from database import SessionLocal, init_db
from models import BusinessUnit, Manager, Ticket, TicketAnalysis, Assignment
from llm import analyze_ticket, get_attachment_context
from geocoding import OFFICE_COORDS
from routing import reset_counters, route_ticket

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LABELS_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "tickets_guid_language_label.csv")

LANGUAGE_LABEL_MAP = {
    "ru": "RU",
    "kk": "KZ",
    "kz": "KZ",
    "en": "ENG",
    "eng": "ENG",
    # The model output taxonomy is RU/KZ/ENG only.
    # Non-standard labels are mapped to RU by current business rule default.
    "uz": "RU",
    "unknown": "RU",
    "latin-other": "RU",
}


def _percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile for small latency samples."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil((p / 100.0) * len(ordered)))
    return ordered[rank - 1]


def _timing_summary_line(name: str, values: list[float]) -> str:
    if not values:
        return f"[Pipeline][Timing] {name}: no samples"
    avg = sum(values) / len(values)
    p95 = _percentile(values, 95)
    mx = max(values)
    return (
        f"[Pipeline][Timing] {name}: "
        f"avg={avg:.3f}s p95={p95:.3f}s max={mx:.3f}s n={len(values)}"
    )


def _normalize_expected_language(label_value: str | None) -> str | None:
    if label_value is None:
        return None
    raw = str(label_value).strip().lower()
    if not raw or raw == "nan":
        return None
    return LANGUAGE_LABEL_MAP.get(raw)


def log_accuracy_from_labels(db: Session):
    """Compare predictions with tickets_guid_language_label.csv and print metrics."""
    if not os.path.exists(LABELS_CSV_PATH):
        print(f"[Pipeline][Accuracy] labels file not found: {LABELS_CSV_PATH}")
        return

    labels: dict[str, dict[str, str]] = {}
    try:
        with open(LABELS_CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            required_cols = {"GUID клиента", "Language", "Label"}
            if not required_cols.issubset(set(reader.fieldnames or [])):
                print(
                    "[Pipeline][Accuracy] labels file has unexpected columns. "
                    "Expected: GUID клиента, Language, Label"
                )
                return

            for row in reader:
                guid = str(row.get("GUID клиента", "")).strip().lower()
                if not guid or guid == "nan":
                    continue
                labels[guid] = {
                    "language": str(row.get("Language", "")).strip(),
                    "label": str(row.get("Label", "")).strip(),
                }
    except Exception as e:
        print(f"[Pipeline][Accuracy] failed to read labels file: {e}")
        return

    if not labels:
        print("[Pipeline][Accuracy] labels file is empty.")
        return

    predictions: dict[str, dict[str, str | None]] = {}
    rows = (
        db.query(Ticket.guid, TicketAnalysis.ticket_type, TicketAnalysis.language)
        .outerjoin(TicketAnalysis, TicketAnalysis.ticket_id == Ticket.id)
        .all()
    )
    for guid, ticket_type, language in rows:
        predictions[str(guid).strip().lower()] = {
            "ticket_type": ticket_type,
            "language": language,
        }

    total_labels = len(labels)
    matched = 0
    missing_in_db = 0
    missing_analysis = 0
    type_correct = 0
    lang_eval = 0
    lang_correct = 0
    lang_unmapped = 0
    per_type_total: dict[str, int] = {}
    per_type_correct: dict[str, int] = {}

    for guid, ref in labels.items():
        pred = predictions.get(guid)
        if pred is None:
            missing_in_db += 1
            continue

        pred_type = pred.get("ticket_type")
        pred_lang = pred.get("language")
        if not pred_type:
            missing_analysis += 1
            continue

        matched += 1
        expected_type = ref["label"]
        per_type_total[expected_type] = per_type_total.get(expected_type, 0) + 1
        if pred_type == expected_type:
            type_correct += 1
            per_type_correct[expected_type] = per_type_correct.get(expected_type, 0) + 1

        expected_lang = _normalize_expected_language(ref["language"])
        if expected_lang is None:
            lang_unmapped += 1
            continue

        lang_eval += 1
        if (pred_lang or "").upper() == expected_lang:
            lang_correct += 1

    type_acc = (type_correct / matched * 100.0) if matched else 0.0
    lang_acc = (lang_correct / lang_eval * 100.0) if lang_eval else 0.0

    print(
        f"[Pipeline][Accuracy] labels={total_labels} matched={matched} "
        f"missing_in_db={missing_in_db} missing_analysis={missing_analysis}"
    )
    print(
        f"[Pipeline][Accuracy] ticket_type={type_correct}/{matched} "
        f"({type_acc:.2f}%)"
    )
    print(
        f"[Pipeline][Accuracy] language={lang_correct}/{lang_eval} "
        f"({lang_acc:.2f}%) unmapped={lang_unmapped}"
    )
    if per_type_total:
        by_type_parts = []
        for ticket_type in sorted(per_type_total.keys()):
            c = per_type_correct.get(ticket_type, 0)
            n = per_type_total[ticket_type]
            by_type_parts.append(f"{ticket_type}:{c}/{n}")
        print(f"[Pipeline][Accuracy] by_type={' | '.join(by_type_parts)}")


def load_business_units(db: Session):
    """Load business_units.csv into DB."""
    path = os.path.join(DATA_DIR, "business_units.csv")
    df = pd.read_csv(path)

    for _, row in df.iterrows():
        office_name = str(row["Офис"]).strip()
        if db.query(BusinessUnit).filter_by(office_name=office_name).first():
            continue
        coords = OFFICE_COORDS.get(office_name, (None, None))
        bu = BusinessUnit(
            office_name=office_name,
            address=str(row["Адрес"]).strip() if pd.notna(row["Адрес"]) else None,
            latitude=coords[0],
            longitude=coords[1],
        )
        db.add(bu)
    db.commit()
    print(f"[Pipeline] Business units loaded.")


def load_managers(db: Session):
    """Load managers.csv into DB."""
    path = os.path.join(DATA_DIR, "managers.csv")
    df = pd.read_csv(path)
    # Strip column names of whitespace
    df.columns = [c.strip() for c in df.columns]

    for _, row in df.iterrows():
        name = str(row["ФИО"]).strip()
        if db.query(Manager).filter_by(full_name=name).first():
            continue

        skills_raw = str(row.get("Навыки", "")).strip()
        skills = [s.strip() for s in skills_raw.split(",") if s.strip()] if skills_raw and skills_raw != "nan" else []

        manager = Manager(
            full_name=name,
            position=str(row.get("Должность", "")).strip(),
            office=str(row.get("Офис", "")).strip(),
            skills=skills,
            current_load=int(row.get("Количество обращений в работе", 0)),
        )
        db.add(manager)
    db.commit()
    print(f"[Pipeline] Managers loaded.")


def load_tickets(db: Session):
    """Load tickets.csv into DB."""
    path = os.path.join(DATA_DIR, "tickets.csv")
    df = pd.read_csv(path, dtype=str)
    df.columns = [c.strip() for c in df.columns]

    loaded = 0
    for _, row in df.iterrows():
        guid = str(row.get("GUID клиента", "")).strip()
        if not guid or guid == "nan":
            continue
        if db.query(Ticket).filter_by(guid=guid).first():
            continue

        birth_raw = str(row.get("Дата рождения", "")).strip()
        birth_date = None
        if birth_raw and birth_raw != "nan":
            try:
                birth_date = datetime.strptime(birth_raw.split(" ")[0], "%Y-%m-%d").date()
            except ValueError:
                pass

        ticket = Ticket(
            guid=guid,
            gender=_clean(row.get("Пол клиента")),
            birth_date=birth_date,
            description=_clean(row.get("Описание")),   # stripped column name
            attachment=_clean(row.get("Вложения")),
            segment=_clean(row.get("Сегмент клиента")),
            country=_clean(row.get("Страна")),
            region=_clean(row.get("Область")),
            city=_clean(row.get("Населённый пункт")),
            street=_clean(row.get("Улица")),
            house=_clean(row.get("Дом")),
        )
        db.add(ticket)
        loaded += 1
    db.commit()
    print(f"[Pipeline] Tickets loaded: {loaded}")


def _clean(val) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    return s if s and s.lower() != "nan" else None


def run_pipeline(progress_callback=None):
    """
    Full pipeline:
    1. Ensure DB tables exist
    2. Load CSVs
    3. LLM analysis + routing for each ticket
    """
    init_db()
    db = SessionLocal()
    try:
        load_business_units(db)
        load_managers(db)
        load_tickets(db)

        tickets = db.query(Ticket).all()
        managers = db.query(Manager).all()

        # Reset routing counters for fresh run
        reset_counters()

        pending_tickets: list[Ticket] = []
        for ticket in tickets:
            if ticket.analysis:
                print(f"[Pipeline] Ticket {ticket.guid} already analyzed, skipping.")
                continue
            pending_tickets.append(ticket)

        total = len(pending_tickets)
        timing_samples: dict[str, list[float]] = {
            "attachment": [],
            "llm": [],
            "routing": [],
            "persist": [],
            "ticket_total": [],
        }
        analysis_engine_counts: dict[str, int] = {}

        for i, ticket in enumerate(pending_tickets):
            if progress_callback:
                progress_callback(i, total, ticket.guid)

            print(f"[Pipeline] Analyzing ticket {i+1}/{total}: {ticket.guid}")
            ticket_started_at = perf_counter()
            stage_started_at = perf_counter()

            # 1a. Attachment processing (vision or missing-attachment detection)
            attachment_ctx = get_attachment_context(
                attachment_filename=ticket.attachment,
                description=ticket.description,
                data_dir=DATA_DIR,
            )
            attachment_time = perf_counter() - stage_started_at
            timing_samples["attachment"].append(attachment_time)
            if attachment_ctx:
                print(f"[Pipeline]   Attachment: {attachment_ctx[:80]}...")

            # 1b. LLM analysis (text + optional attachment context)
            stage_started_at = perf_counter()
            try:
                result = analyze_ticket(
                    description=ticket.description or "",
                    segment=ticket.segment or "Mass",
                    country=ticket.country or "",
                    attachment_context=attachment_ctx,
                )
            except Exception as e:
                print(f"[Pipeline] LLM error for {ticket.guid}: {e}")
                result = {
                    "ticket_type": "Консультация",
                    "sentiment": "Нейтральный",
                    "priority": 5,
                    "language": "RU",
                    "summary": "Ошибка анализа ИИ.",
                    "recommendation": "Требуется ручная обработка.",
                    "analysis_engine": "fallback:pipeline_exception",
                }
            llm_time = perf_counter() - stage_started_at
            timing_samples["llm"].append(llm_time)
            analysis_engine = result.get("analysis_engine", "llm:unknown")
            analysis_engine_counts[analysis_engine] = analysis_engine_counts.get(analysis_engine, 0) + 1
            is_spam = result.get("ticket_type") == "Спам"

            if is_spam:
                # Spam tickets are analytics-only: no routing/assignment and no priority.
                result["priority"] = None
                result["sentiment"] = "Нейтральный"
                routing_time = 0.0
                manager, office, lat, lon, rr_index = (None, None, None, None, None)
            else:
                # 2. Routing
                stage_started_at = perf_counter()
                manager, office, lat, lon, rr_index = route_ticket(
                    managers=managers,
                    country=ticket.country,
                    city=ticket.city,
                    region=ticket.region,
                    street=ticket.street,
                    house=ticket.house,
                    segment=ticket.segment or "Mass",
                    ticket_type=result.get("ticket_type", "Консультация"),
                    language=result.get("language", "RU"),
                    sentiment=result.get("sentiment", "Нейтральный"),
                )
                routing_time = perf_counter() - stage_started_at

            timing_samples["routing"].append(routing_time)

            # 3. Persist analysis
            stage_started_at = perf_counter()
            analysis = TicketAnalysis(
                ticket_id=ticket.id,
                ticket_type=result.get("ticket_type"),
                sentiment=result.get("sentiment"),
                priority_score=None if is_spam else result.get("priority"),
                language=result.get("language"),
                summary=result.get("summary"),
                recommendation=result.get("recommendation"),
                client_lat=lat,
                client_lon=lon,
                nearest_office=office,
                attachment_description=attachment_ctx,
            )
            db.add(analysis)

            # 4. Persist assignment + increment manager load
            if manager:
                assignment = Assignment(
                    ticket_id=ticket.id,
                    manager_id=manager.id,
                    assigned_office=office,
                    round_robin_index=rr_index,
                )
                db.add(assignment)
                manager.current_load += 1

            db.commit()
            persist_time = perf_counter() - stage_started_at
            timing_samples["persist"].append(persist_time)

            total_ticket_time = perf_counter() - ticket_started_at
            timing_samples["ticket_total"].append(total_ticket_time)

            print(
                f"[Pipeline][Timing] ticket={ticket.guid[:8]} "
                f"attachment={attachment_time:.3f}s "
                f"llm={llm_time:.3f}s "
                f"routing={routing_time:.3f}s "
                f"persist={persist_time:.3f}s "
                f"total={total_ticket_time:.3f}s "
                f"engine={analysis_engine}"
            )
            if is_spam:
                print(f"[Pipeline]   Spam policy: no manager assignment, priority=None.")
            print(f"[Pipeline] → {result.get('ticket_type')} | {result.get('language')} | office={office} | manager={manager.full_name if manager else 'NONE'}")

        print(_timing_summary_line("attachment", timing_samples["attachment"]))
        print(_timing_summary_line("llm", timing_samples["llm"]))
        print(_timing_summary_line("routing", timing_samples["routing"]))
        print(_timing_summary_line("persist", timing_samples["persist"]))
        print(_timing_summary_line("ticket_total", timing_samples["ticket_total"]))
        print(f"[Pipeline][Timing] analysis_engine_counts={analysis_engine_counts}")
        log_accuracy_from_labels(db)
        print("[Pipeline] Done!")
    finally:
        db.close()


if __name__ == "__main__":
    run_pipeline()
