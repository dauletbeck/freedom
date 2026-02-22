"""
llm_local.py — Local LLM variant using Qwen2.5 7B Instruct via Ollama.

Drop-in replacement for llm.py, adapted for a non-reasoning local model:
  - No reasoning_effort parameter
  - max_tokens instead of max_completion_tokens
  - response_format={"type": "json_object"} (Ollama doesn't support json_schema)
  - Explicit JSON example at the end of the system prompt (Qwen follows examples well)
  - Optional image analysis via a separate VL model (LOCAL_LLM_VISION_MODEL)

Usage:
  # Pull the model first (one-time):
  ollama pull qwen2.5:7b-instruct

  # Start Ollama (if not already running):
  ollama serve

  # Use as a module:
  from llm_local import analyze_ticket, get_attachment_context, run_assistant_query
"""

import os
import json
import re
import io
import base64
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Client — Ollama exposes an OpenAI-compatible API at port 11434.
# Override via env vars to point at LM Studio, vLLM, or any other local server.
# ---------------------------------------------------------------------------
LOCAL_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
LOCAL_API_KEY = os.getenv("LOCAL_LLM_API_KEY", "ollama")  # Ollama ignores the key

client = OpenAI(
    api_key=LOCAL_API_KEY,
    base_url=LOCAL_BASE_URL,
)

# Ollama model tag — pull with: ollama pull qwen2.5:7b-instruct
MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen2.5:7b-instruct")
ASSISTANT_MODEL = os.getenv("LOCAL_LLM_ASSISTANT_MODEL", MODEL)
VISION_MODEL = os.getenv("LOCAL_LLM_VISION_MODEL", "qwen2.5vl:7b")
ENABLE_VISION = os.getenv("LOCAL_LLM_ENABLE_VISION", "true").lower() in {"1", "true", "yes", "on"}

# Qwen2.5-7B is fast locally; keep token budgets tight to avoid slow responses.
TICKET_MAX_TOKENS = int(os.getenv("LOCAL_LLM_TICKET_MAX_TOKENS", "512"))
ASSISTANT_MAX_TOKENS = int(os.getenv("LOCAL_LLM_ASSISTANT_MAX_TOKENS", "1024"))
VISION_MAX_TOKENS = int(os.getenv("LOCAL_LLM_VISION_MAX_TOKENS", "220"))

MAX_DESCRIPTION_CHARS = int(os.getenv("LOCAL_LLM_MAX_DESCRIPTION_CHARS", "1200"))
MAX_ATTACHMENT_CTX_CHARS = int(os.getenv("LOCAL_LLM_MAX_ATTACHMENT_CTX_CHARS", "700"))
IMAGE_MAX_SIDE_PX = int(os.getenv("LOCAL_LLM_IMAGE_MAX_SIDE_PX", "768"))

ATTACHMENTS_SUBDIR = "images"
DEFAULT_IMAGE_EXT = ".png"

# ---------------------------------------------------------------------------
# Ticket type constants (shared with routing.py)
# ---------------------------------------------------------------------------
TICKET_TYPES = [
    "Жалоба",
    "Смена данных",
    "Консультация",
    "Претензия",
    "Неработоспособность приложения",
    "Мошеннические действия",
    "Спам",
]

# ---------------------------------------------------------------------------
# Fast heuristics (identical to llm.py — language-independent)
# ---------------------------------------------------------------------------
ATTACHMENT_REF_KEYWORDS = [
    "вложени", "скрин", "screenshot", "attached", "attachment",
    "см. скрин", "фото", "photo", "картинк", "изображени", "прикреп",
]
SPAM_KEYWORDS = [
    "выгодное предложение", "акция", "скидк", "реклама",
    "оборудовани", "в наличии", "купите", "продаж",
]
FRAUD_KEYWORDS = [
    "мошен", "мошенник", "скам", "scam", "развод", "обман",
    "фишинг", "phishing", "не санкционирован", "несанкционирован",
    "неизвестн", "без моего ведома", "без моего согласия",
    "украли", "украден", "взлом", "поддел", "подмена реквизитов",
    "подозрительн", "чужой перевод",
]
DATA_CHANGE_KEYWORDS = [
    "смен", "измен", "обнов", "номер телефона", "телефон",
    "паспорт", "email", "e-mail", "адрес", "почт",
]
APP_ISSUE_KEYWORDS = [
    "не могу войти", "не могу зайти", "не работает", "ошибк",
    "app", "приложен", "сбой", "bug", "крэш", "crash",
    "смс", "парол", "восстановлен",
]
CLAIM_KEYWORDS = [
    "претензи", "требую", "верните деньги", "возврат",
    "компенсац", "в суд", "жалоба в",
]
NEGATIVE_KEYWORDS = [
    "срочно", "не работает", "ошибка", "невозможно",
    "неправомерно", "возмущен", "жалоба", "проблема", "заблок",
]
LOSS_RISK_KEYWORDS = [
    "потерял деньги", "потеряла деньги", "потеря денег", "потеря прибыли",
    "убыт", "пропали деньги", "деньги исчезли", "списали деньги",
    "списание без", "не пришли деньги", "не поступили деньги",
    "не получил деньги", "не получила деньги", "не могу вывести",
    "не выводятся", "застряли деньги", "lost money", "funds missing",
    "profit loss",
]
LEGAL_RISK_KEYWORDS = [
    "суд", "иск", "юрист", "адвокат", "прокурат", "регулятор",
    "комитет", "цб", "нацбанк", "арбитраж", "litigation",
]
ACCOUNT_BLOCK_KEYWORDS = [
    "заблок", "блокиров", "замороз", "ограничен", "restricted", "blocked",
]
LARGE_SUM_KEYWORDS = [
    "большая сумма", "крупная сумма", "миллион", "млн", "large amount",
]
CURRENCY_MARKERS = ["тенге", "kzt", "₸", "usd", "$", "eur", "€", "доллар", "руб", "₽"]

URL_PATTERN = re.compile(r"https?://|www\.", flags=re.IGNORECASE)
LATIN_PATTERN = re.compile(r"[a-zA-Z]")
CYRILLIC_PATTERN = re.compile(r"[а-яА-ЯёЁ]")
KZ_SPECIFIC_PATTERN = re.compile(r"[әіңғүұқөһӘІҢҒҮҰҚӨҺ]")
AZ_LATIN_PATTERN = re.compile(r"ı")
UZ_LATIN_PATTERN = re.compile(r"ʻ")
UZ_CYRILLIC_PATTERN = re.compile(r"[ҶҷӮӯ]")
NUMBER_PATTERN = re.compile(r"\b\d[\d\s]{2,}\b")

# ---------------------------------------------------------------------------
# System prompt — adapted for Qwen2.5 7B Instruct.
#
# Key differences from llm.py:
#   1. Shorter, more imperative phrasing (Qwen is a chat model, not a reasoner).
#   2. Explicit "Output ONLY the JSON" instruction at the top AND bottom.
#   3. Full JSON example at the end — Qwen follows concrete examples very reliably.
#   4. No XML-style tags (the original used them for clarity; they work fine with Qwen
#      but a flat numbered list tends to be more robust for 7B-scale models).
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a ticket classifier for Freedom Finance (Kazakhstan brokerage).
Read the support ticket and output ONLY a JSON object — no explanation, no markdown, no extra text.

TICKET_TYPE — choose exactly one:
1. "Жалоба"                         — general dissatisfaction, no demand for money
2. "Претензия"                      — formal claim demanding refund/compensation ("требую", "верните", "претензия")
3. "Смена данных"                   — request to change phone, passport, address, or email
4. "Консультация"                   — question or information request ONLY when there is no scam/loss/risk signal
5. "Неработоспособность приложения" — app crash, login failure, broken feature, technical error
6. "Мошеннические действия"         — fraud, unauthorized transaction, phishing, suspicious activity
7. "Спам"                           — promo offer, ad, or sales pitch unrelated to the client account

DECISION PRIORITY (stop at first match):
1. "Спам"
2. "Мошеннические действия" — external fraud/unauthorized transfer/phishing/suspicious third party
3. "Смена данных"
4. "Претензия" — explicit demand for refund/compensation/cancellation
5. "Неработоспособность приложения"
6. "Жалоба"
7. "Консультация" — only if purely informational

CONSULTATION GUARDRAIL:
- Use "Консультация" only if the ticket asks for explanation/instructions and has no red flags.
- Red flags: missing money, loss/profit loss, unauthorized transfer, suspicious third party, blocked/disappeared funds, request to investigate or return money.
- If red flags exist, do NOT use "Консультация"; choose "Мошеннические действия" or "Жалоба/Претензия".

SENTIMENT — choose exactly one:
- "Позитивный" — satisfied or grateful
- "Нейтральный" — factual / neutral (always use for Спам)
- "Негативный"  — angry, frustrated, upset

LANGUAGE — write the full language name in English:
- If text contains ә і ң ғ ү ұ қ ө һ → "Kazakh"
- If text is English → "English"
- If text is Russian (or unrecognized) → "Russian"
- Other: "Uzbek", "Azerbaijani", etc.

PRIORITY — integer 1–10, or null for Спам:
  Base: Мошеннические действия=9, Претензия=8, Жалоба=6, Неработоспособность=6,
        Смена данных=5, Консультация=3, Спам=null
  Add +2 if segment is VIP or Priority (floor 6); +1 if Негативный; +1 if legal action / large sum.
  Cap at 10.

SUMMARY — 1–2 sentences in Russian describing the issue.
RECOMMENDATION — 1 sentence in Russian telling the manager what to do.

Output format (JSON only, no other text):
{"ticket_type": "...", "sentiment": "...", "priority": 5, "language": "...", "summary": "...", "recommendation": "..."}"""


# ---------------------------------------------------------------------------
# Helper utilities (identical to llm.py)
# ---------------------------------------------------------------------------

def references_attachment(description: str) -> bool:
    if not description:
        return False
    desc_lower = description.lower()
    return any(kw in desc_lower for kw in ATTACHMENT_REF_KEYWORDS)


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(kw in text for kw in keywords)


def _infer_language(description: str) -> str:
    if not description:
        return "RU"
    if KZ_SPECIFIC_PATTERN.search(description):
        return "KZ"
    if UZ_CYRILLIC_PATTERN.search(description):
        return "RU"
    latin_count = len(LATIN_PATTERN.findall(description))
    cyr_count = len(CYRILLIC_PATTERN.findall(description))
    if latin_count >= 20 and latin_count > cyr_count:
        if AZ_LATIN_PATTERN.search(description):
            return "RU"
        if UZ_LATIN_PATTERN.search(description):
            return "RU"
        return "ENG"
    return "RU"


def _normalize_language(lang: str) -> str:
    lower = (lang or "").strip().lower()
    if lower in {"kazakh", "kz", "казахский", "kazak", "qazaq", "қазақша"}:
        return "KZ"
    if lower in {"english", "eng", "en", "английский"}:
        return "ENG"
    return "RU"


def _infer_sentiment(text_lower: str, ticket_type: str) -> str:
    if ticket_type in {"Претензия", "Жалоба", "Мошеннические действия"}:
        return "Негативный"
    if _contains_any(text_lower, NEGATIVE_KEYWORDS):
        return "Негативный"
    return "Нейтральный"


def _base_priority(ticket_type: str) -> int:
    return {
        "Мошеннические действия": 9,
        "Претензия": 8,
        "Жалоба": 6,
        "Неработоспособность приложения": 6,
        "Смена данных": 5,
        "Консультация": 3,
        "Спам": 1,
    }.get(ticket_type, 5)


def _mentions_large_sum(text_lower: str) -> bool:
    if _contains_any(text_lower, LARGE_SUM_KEYWORDS):
        return True

    has_currency = _contains_any(text_lower, CURRENCY_MARKERS)
    for raw in NUMBER_PATTERN.findall(text_lower):
        digits = raw.replace(" ", "")
        if not digits.isdigit():
            continue
        value = int(digits)
        # High absolute amount, or medium amount when currency is explicitly mentioned.
        if value >= 1_000_000:
            return True
        if has_currency and value >= 300_000:
            return True
    return False


def _has_high_impact_signal(description: str, attachment_context: str | None = None) -> bool:
    text_lower = f"{description or ''} {attachment_context or ''}".lower()
    return (
        _contains_any(text_lower, LEGAL_RISK_KEYWORDS)
        or _contains_any(text_lower, ACCOUNT_BLOCK_KEYWORDS)
        or _mentions_large_sum(text_lower)
    )


def _has_loss_risk_signal(description: str, attachment_context: str | None = None) -> bool:
    text_lower = f"{description or ''} {attachment_context or ''}".lower()
    return _contains_any(text_lower, LOSS_RISK_KEYWORDS)


def _apply_consultation_guardrail(
    ticket_type: str,
    description: str,
    attachment_context: str | None = None,
) -> str:
    if ticket_type != "Консультация":
        return ticket_type

    text_lower = f"{description or ''} {attachment_context or ''}".lower()
    if _contains_any(text_lower, FRAUD_KEYWORDS):
        return "Мошеннические действия"
    if _has_loss_risk_signal(description, attachment_context) or _has_high_impact_signal(description, attachment_context):
        return "Жалоба"
    return ticket_type


def _compute_priority(
    ticket_type: str,
    sentiment: str,
    segment: str,
    description: str,
    attachment_context: str | None = None,
) -> int | None:
    if ticket_type == "Спам":
        return None

    priority = _base_priority(ticket_type)
    if (segment or "").strip().lower() in {"vip", "priority"}:
        priority = max(priority + 2, 6)
    if sentiment == "Негативный":
        priority += 1
    if _has_high_impact_signal(description, attachment_context):
        priority += 1
    return max(1, min(10, priority))


def _default_summary(description: str, attachment_context: str | None = None) -> str:
    summary_parts = []
    if description and description.strip():
        summary_parts.append(_truncate_text(description.replace("\n", " ").strip(), 180))
    else:
        summary_parts.append("Текст обращения отсутствует.")
    if attachment_context:
        summary_parts.append("Есть вложение со скриншотом.")
    return " ".join(summary_parts)


def _default_recommendation(ticket_type: str) -> str:
    recommendation_map = {
        "Спам": "Закрыть как спам и не передавать в работу менеджеру.",
        "Мошеннические действия": "Срочно эскалировать в антифрод и временно ограничить рисковые операции.",
        "Неработоспособность приложения": "Передать в техподдержку приложения и проверить логи авторизации/операций.",
        "Смена данных": "Запросить подтверждающие документы и провести обновление данных клиента.",
        "Претензия": "Передать старшему менеджеру для официального ответа и проверки оснований требований.",
        "Жалоба": "Проверить ситуацию по счету и подготовить клиенту разъяснение/решение.",
        "Консультация": "Дать клиенту инструкцию и уточнить детали запроса при необходимости.",
    }
    return recommendation_map.get(ticket_type, recommendation_map["Консультация"])


def _ensure_summary_and_recommendation(
    result: dict,
    description_for_summary: str,
    attachment_context: str | None = None,
) -> None:
    summary = result.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        result["summary"] = _default_summary(description_for_summary, attachment_context)
    else:
        result["summary"] = summary.strip()

    recommendation = result.get("recommendation")
    if not isinstance(recommendation, str) or not recommendation.strip():
        result["recommendation"] = _default_recommendation(result.get("ticket_type", "Консультация"))
    else:
        result["recommendation"] = recommendation.strip()


def _build_heuristic_result(
    description: str,
    segment: str,
    ticket_type: str,
    reason: str,
    attachment_context: str | None = None,
) -> dict:
    text_lower = (description or "").lower()
    if ticket_type == "Спам":
        sentiment = "Нейтральный"
    else:
        sentiment = _infer_sentiment(text_lower, ticket_type)
    priority = _compute_priority(ticket_type, sentiment, segment, description or "", attachment_context)

    return {
        "ticket_type": ticket_type,
        "sentiment": sentiment,
        "priority": priority,
        "language": _infer_language(description or ""),
        "summary": _default_summary(description, attachment_context),
        "recommendation": _default_recommendation(ticket_type),
        "analysis_engine": f"heuristic:{reason}",
    }


def _try_fast_rule_based_classification(
    description: str,
    segment: str,
    attachment_context: str | None = None,
) -> dict | None:
    text = f"{description or ''} {attachment_context or ''}".strip()
    if not text:
        return None
    text_lower = text.lower()
    has_url = bool(URL_PATTERN.search(text))

    if has_url and _contains_any(text_lower, SPAM_KEYWORDS):
        return _build_heuristic_result(text, segment, "Спам", "spam", attachment_context)
    if _contains_any(text_lower, FRAUD_KEYWORDS):
        return _build_heuristic_result(text, segment, "Мошеннические действия", "fraud", attachment_context)
    if _contains_any(text_lower, CLAIM_KEYWORDS):
        return _build_heuristic_result(text, segment, "Претензия", "claim", attachment_context)
    if _contains_any(text_lower, DATA_CHANGE_KEYWORDS) and (
        "номер" in text_lower or "паспорт" in text_lower or "email" in text_lower or "адрес" in text_lower
    ):
        return _build_heuristic_result(text, segment, "Смена данных", "data_change", attachment_context)
    if _contains_any(text_lower, APP_ISSUE_KEYWORDS):
        return _build_heuristic_result(text, segment, "Неработоспособность приложения", "app_issue", attachment_context)
    if _has_loss_risk_signal(text, attachment_context) or _has_high_impact_signal(text, attachment_context):
        return _build_heuristic_result(text, segment, "Жалоба", "loss_or_risk_signal", attachment_context)
    if "!" in text and _contains_any(text_lower, NEGATIVE_KEYWORDS):
        return _build_heuristic_result(text, segment, "Жалоба", "complaint", attachment_context)
    return None


# ---------------------------------------------------------------------------
# Vision (optional, uses a dedicated VL model)
# ---------------------------------------------------------------------------

VISION_PROMPT = (
    "Это скриншот из брокерского приложения клиента. "
    "Кратко (1-2 предложения, на русском) опиши, какая ошибка/проблема на экране "
    "и что именно у клиента не получается сделать."
)


def _resize_image_bytes(image_path: str) -> tuple[bytes, str]:
    from PIL import Image

    with Image.open(image_path) as img:
        img = img.convert("RGB")
        width, height = img.size
        max_side = max(width, height)
        if max_side > IMAGE_MAX_SIDE_PX:
            scale = IMAGE_MAX_SIDE_PX / max_side
            new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
            img = img.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue(), "image/jpeg"


def analyze_image(image_path: str) -> str:
    """Analyze an image attachment with a dedicated local VL model via Ollama."""
    if not os.path.exists(image_path):
        return f"[Файл вложения не найден: {os.path.basename(image_path)}]"

    if not ENABLE_VISION:
        return f"[Анализ изображения отключен: LOCAL_LLM_ENABLE_VISION=false, файл={os.path.basename(image_path)}]"
    if not (VISION_MODEL or "").strip():
        return "[Анализ изображения недоступен: LOCAL_LLM_VISION_MODEL не задан]"

    try:
        img_bytes, mime = _resize_image_bytes(image_path)
        img_data = base64.standard_b64encode(img_bytes).decode("utf-8")
    except Exception as err:
        return f"[Ошибка подготовки изображения: {err}]"

    try:
        response = client.chat.completions.create(
            model=VISION_MODEL,
            max_tokens=VISION_MAX_TOKENS,
            temperature=0.1,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{img_data}",
                                "detail": "low",
                            },
                        },
                    ],
                }
            ],
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            return f"[Пустой ответ vision-модели {VISION_MODEL}]"
        return content
    except Exception as err:
        return f"[Ошибка анализа изображения моделью {VISION_MODEL}: {err}]"


def _resolve_attachment_path(attachment_filename: str, data_dir: str) -> str | None:
    raw_name = attachment_filename.strip()
    if not raw_name:
        return None
    normalized = os.path.normpath(raw_name).replace("\\", "/")
    basename = os.path.basename(normalized)
    images_dir = os.path.join(data_dir, ATTACHMENTS_SUBDIR)
    candidates: list[str] = []

    def add(path: str):
        if path not in candidates:
            candidates.append(path)

    parts = normalized.split("/")
    if not os.path.isabs(normalized) and ".." not in parts:
        add(os.path.join(data_dir, normalized))
    add(os.path.join(images_dir, basename))
    add(os.path.join(data_dir, basename))

    name_root, ext = os.path.splitext(basename)
    if basename and not ext:
        add(os.path.join(images_dir, f"{name_root}{DEFAULT_IMAGE_EXT}"))
        add(os.path.join(data_dir, f"{name_root}{DEFAULT_IMAGE_EXT}"))

    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def get_attachment_context(
    attachment_filename: str | None,
    description: str | None,
    data_dir: str,
) -> str | None:
    if attachment_filename:
        image_path = _resolve_attachment_path(attachment_filename, data_dir)
        if image_path:
            description_text = analyze_image(image_path)
            rel_path = os.path.relpath(image_path, data_dir).replace("\\", "/")
            return f"Вложение '{rel_path}': {description_text}"
        return (
            f"⚠️ Указан файл вложения '{attachment_filename}', "
            f"но файл не найден в 'data/{ATTACHMENTS_SUBDIR}/' (или legacy пути data/)."
        )
    if references_attachment(description):
        return (
            "⚠️ Клиент упоминает вложение или скриншот в тексте обращения, "
            "но файл вложения не был прикреплён."
        )
    return None


# ---------------------------------------------------------------------------
# Main ticket analysis
# ---------------------------------------------------------------------------

def analyze_ticket(
    description: str,
    segment: str,
    country: str,
    attachment_context: str | None = None,
) -> dict:
    """Classify a ticket using the local Qwen2.5-7B-Instruct model."""
    has_text = description and description.strip()

    if not has_text and not attachment_context:
        return {
            "ticket_type": "Консультация",
            "sentiment": "Нейтральный",
            "priority": _compute_priority("Консультация", "Нейтральный", segment or "Mass", "", None),
            "language": "RU",
            "summary": "Обращение без текстового описания и вложения.",
            "recommendation": "Связаться с клиентом для уточнения запроса.",
            "analysis_engine": "fallback:empty",
        }

    # Always try fast heuristics first — saves LLM calls on obvious cases.
    heuristic = _try_fast_rule_based_classification(
        description=description or "",
        segment=segment or "Mass",
        attachment_context=attachment_context,
    )
    if heuristic is not None:
        _ensure_summary_and_recommendation(
            heuristic,
            description_for_summary=description or "",
            attachment_context=attachment_context,
        )
        return heuristic

    description_for_llm = _truncate_text(description or "", MAX_DESCRIPTION_CHARS)
    attachment_section = ""
    if attachment_context:
        ctx = _truncate_text(attachment_context, MAX_ATTACHMENT_CTX_CHARS)
        attachment_section = f"\nAttachment context:\n{ctx}\n"

    if not has_text and attachment_context:
        description_for_llm = "(Описание отсутствует — информация из вложения выше)"

    # User message — keep it compact and imperative for Qwen.
    # Repeating the output schema in the user turn increases compliance for 7B models.
    user_message = f"""Classify this support ticket. Output ONLY valid JSON.

Segment: {segment or 'Mass'}
Country: {country or 'Unknown'}
Description:
{description_for_llm}
{attachment_section}
Output exactly:
{{"ticket_type": "...", "sentiment": "...", "priority": <int or null>, "language": "...", "summary": "...", "recommendation": "..."}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=TICKET_MAX_TOKENS,
            # json_object mode tells Ollama/Qwen to guarantee valid JSON output.
            # (json_schema is an OpenAI-only extension not supported by Ollama.)
            response_format={"type": "json_object"},
            temperature=0.1,  # near-deterministic for classification
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError(
                f"Empty response from local LLM — finish_reason={response.choices[0].finish_reason!r}"
            )

        result = json.loads(content)
        result["language"] = _normalize_language(result.get("language", ""))
        result["analysis_engine"] = f"local:{MODEL}"

    except Exception as err:
        print(f"[LLM_LOCAL] Error: {err}. Returning deterministic fallback.")
        fallback_type = "Консультация"
        heuristic_fallback = _try_fast_rule_based_classification(
            description=description or "",
            segment=segment or "Mass",
            attachment_context=attachment_context,
        )
        if heuristic_fallback is not None:
            fallback_type = heuristic_fallback.get("ticket_type", fallback_type)
        fallback_type = _apply_consultation_guardrail(fallback_type, description or "", attachment_context)
        fallback_sentiment = _infer_sentiment((description or "").lower(), fallback_type)
        if fallback_type == "Спам":
            fallback_sentiment = "Нейтральный"
        result = {
            "ticket_type": fallback_type,
            "sentiment": fallback_sentiment,
            "priority": _compute_priority(
                fallback_type,
                fallback_sentiment,
                segment or "Mass",
                description or "",
                attachment_context,
            ),
            "language": _infer_language(description or ""),
            "summary": "Ошибка локального LLM анализа. Требуется ручная проверка обращения.",
            "recommendation": "Провести ручную классификацию и проверить доступность локального LLM-сервиса.",
            "analysis_engine": "fallback:local_llm_error",
        }
        _ensure_summary_and_recommendation(
            result,
            description_for_summary=description or "",
            attachment_context=attachment_context,
        )
        return result

    # Validate required fields
    valid_types = set(TICKET_TYPES)
    valid_sentiments = {"Позитивный", "Нейтральный", "Негативный"}

    if result.get("ticket_type") not in valid_types:
        result["ticket_type"] = "Консультация"
    result["ticket_type"] = _apply_consultation_guardrail(
        result.get("ticket_type", "Консультация"),
        description or "",
        attachment_context,
    )
    if result.get("sentiment") not in valid_sentiments:
        result["sentiment"] = _infer_sentiment((description or "").lower(), result.get("ticket_type", "Консультация"))
    if result.get("ticket_type") == "Спам":
        result["sentiment"] = "Нейтральный"
    result["priority"] = _compute_priority(
        result.get("ticket_type", "Консультация"),
        result.get("sentiment", "Нейтральный"),
        segment or "Mass",
        description or "",
        attachment_context,
    )
    _ensure_summary_and_recommendation(
        result,
        description_for_summary=description or "",
        attachment_context=attachment_context,
    )
    result.setdefault("analysis_engine", f"local:{MODEL}")
    return result


# ---------------------------------------------------------------------------
# Assistant query (NL → SQL → chart)
# ---------------------------------------------------------------------------

def run_assistant_query(query: str, db_context: str) -> dict:
    """Run a natural language query and return chart instructions."""
    system = """You are a data analyst for the FIRE ticket routing system.
You have a PostgreSQL database with these tables:
- tickets (id, guid, gender, birth_date, description, attachment, segment, country, region, city, street, house)
- ticket_analysis (id, ticket_id, ticket_type, sentiment, priority_score, language, summary, recommendation, attachment_description, client_lat, client_lon, nearest_office, analyzed_at)
- managers (id, full_name, position, office, skills, current_load)
- business_units (id, office_name, address, latitude, longitude)
- assignments (id, ticket_id, manager_id, assigned_office, round_robin_index, assigned_at)

Output ONLY valid JSON (no markdown, no explanation):
{"answer": "brief explanation in Russian", "sql": "SELECT label, value FROM ...", "chart_type": "bar|pie|line|table", "chart_title": "Title in Russian"}

The SQL must return exactly 2 columns named label (text) and value (number)."""

    try:
        response = client.chat.completions.create(
            model=ASSISTANT_MODEL,
            max_tokens=ASSISTANT_MAX_TOKENS,
            response_format={"type": "json_object"},
            temperature=0.1,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Query: {query}\n\nData summary:\n{db_context}"},
            ],
        )
        content = response.choices[0].message.content or ""
        return json.loads(content)
    except json.JSONDecodeError as e:
        content = response.choices[0].message.content if "response" in dir() else ""
        return {
            "answer": content or f"JSON parse error: {e}",
            "sql": None,
            "chart_type": "table",
            "chart_title": "Результат запроса",
        }
    except Exception as e:
        return {
            "answer": f"Ошибка локального LLM: {e}",
            "sql": None,
            "chart_type": "table",
            "chart_title": "Ошибка",
        }


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"[llm_local] Model: {MODEL}  Base URL: {LOCAL_BASE_URL}")
    test_ticket = {
        "description": "Не могу войти в приложение, пишет ошибка авторизации. Срочно!",
        "segment": "Mass",
        "country": "Kazakhstan",
    }
    print("[llm_local] Test ticket:", test_ticket)
    result = analyze_ticket(**test_ticket)
    print("[llm_local] Result:", json.dumps(result, ensure_ascii=False, indent=2))
