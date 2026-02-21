import io
import os
import json
import base64
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# OpenAI-compatible client.
client = OpenAI(
    api_key=os.getenv("LLM_API_KEY", ""),
    base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
)

MODEL = os.getenv("LLM_MODEL", "gpt-5-nano")
ASSISTANT_MODEL = os.getenv("LLM_ASSISTANT_MODEL", MODEL)

# gpt-5-nano is a reasoning model — max_completion_tokens covers BOTH reasoning chain tokens
# and the final output tokens.  The reasoning chain alone can use 500–1000 tokens before
# the JSON appears, so we need a generous cap.  2048 is safe for classification; 4096 for assistant.
TICKET_MAX_TOKENS = int(os.getenv("LLM_TICKET_MAX_TOKENS", "2048"))
ASSISTANT_MAX_TOKENS = int(os.getenv("LLM_ASSISTANT_MAX_TOKENS", "4096"))
def _optional_timeout(env_name: str) -> float | None:
    raw = os.getenv(env_name)
    if raw is None or not raw.strip():
        return None
    try:
        return float(raw)
    except ValueError:
        print(f"[LLM] Invalid {env_name}='{raw}', ignoring timeout.")
        return None


DEFAULT_TIMEOUT_SEC = _optional_timeout("LLM_TIMEOUT_SEC")
TICKET_TIMEOUT_SEC = _optional_timeout("LLM_TICKET_TIMEOUT_SEC")
if TICKET_TIMEOUT_SEC is None:
    TICKET_TIMEOUT_SEC = DEFAULT_TIMEOUT_SEC
ASSISTANT_TIMEOUT_SEC = _optional_timeout("LLM_ASSISTANT_TIMEOUT_SEC")
if ASSISTANT_TIMEOUT_SEC is None:
    ASSISTANT_TIMEOUT_SEC = DEFAULT_TIMEOUT_SEC
MAX_DESCRIPTION_CHARS = int(os.getenv("LLM_MAX_DESCRIPTION_CHARS", "1200"))
MAX_ATTACHMENT_CTX_CHARS = int(os.getenv("LLM_MAX_ATTACHMENT_CTX_CHARS", "700"))
ENABLE_FAST_HEURISTICS = os.getenv("LLM_FAST_HEURISTICS", "false").lower() in {"1", "true", "yes", "on"}

TICKET_TYPES = [
    "Жалоба",
    "Смена данных",
    "Консультация",
    "Претензия",
    "Неработоспособность приложения",
    "Мошеннические действия",
    "Спам",
]

# Keywords that suggest a user is referencing an attachment in their description.
# If these appear but the attachment field is empty, it's an edge case.
ATTACHMENT_REF_KEYWORDS = [
    "вложени",   # вложении, вложение
    "скрин",     # скрин, скриншот, скрин-шот
    "screenshot",
    "attached",
    "attachment",
    "см. скрин",
    "фото",
    "photo",
    "картинк",   # картинка, картинке
    "изображени", # изображение
    "прикреп",   # прикреплен, прикрепил
]

SPAM_KEYWORDS = [
    "выгодное предложение",
    "акция",
    "скидк",
    "реклама",
    "оборудовани",
    "в наличии",
    "купите",
    "продаж",
]

FRAUD_KEYWORDS = [
    "мошен",
    "фишинг",
    "phishing",
    "не санкционирован",
    "несанкционирован",
    "неизвестн",
    "украли",
    "взлом",
    "подозрительн",
    "чужой перевод",
]

DATA_CHANGE_KEYWORDS = [
    "смен",
    "измен",
    "обнов",
    "номер телефона",
    "телефон",
    "паспорт",
    "email",
    "e-mail",
    "адрес",
    "почт",
]

APP_ISSUE_KEYWORDS = [
    "не могу войти",
    "не могу зайти",
    "не работает",
    "ошибк",
    "app",
    "приложен",
    "сбой",
    "bug",
    "крэш",
    "crash",
    "смс",
    "парол",
    "восстановлен",
]

CLAIM_KEYWORDS = [
    "претензи",
    "требую",
    "верните деньги",
    "возврат",
    "компенсац",
    "в суд",
    "жалоба в",
]

NEGATIVE_KEYWORDS = [
    "срочно",
    "не работает",
    "ошибка",
    "невозможно",
    "неправомерно",
    "возмущен",
    "жалоба",
    "проблема",
    "заблок",
]

URL_PATTERN = re.compile(r"https?://|www\.", flags=re.IGNORECASE)
LATIN_PATTERN = re.compile(r"[a-zA-Z]")
CYRILLIC_PATTERN = re.compile(r"[а-яА-ЯёЁ]")
KZ_SPECIFIC_PATTERN = re.compile(r"[әіңғүұқөһӘІҢҒҮҰҚӨҺ]")

# Language disambiguation patterns for Turkic Latin scripts.
# ı (U+0131 dotless i) is the most reliable Azerbaijani Latin marker — absent from Kazakh Latin 2021.
AZ_LATIN_PATTERN = re.compile(r"ı")           # U+0131 — Azerbaijani Latin
# ʻ (U+02BB modifier letter turned comma) is unique to Uzbek Latin orthography (oʻ, gʻ).
UZ_LATIN_PATTERN = re.compile(r"ʻ")           # U+02BB — Uzbek Latin
# Kazakh Cyrillic Ҷ (U+0546) does not appear in Kazakh; it's distinctly Uzbek Cyrillic.
UZ_CYRILLIC_PATTERN = re.compile(r"[ҶҷӮӯ]")  # Ҷ = palatal affricate, Ӯ = Uzbek Cyrillic oʻ

SYSTEM_PROMPT = """You are a customer support classifier for Freedom Finance (Фридом Финанс), a brokerage firm in Kazakhstan. Read the support ticket and output JSON. Do not output anything else.

<ticket_types>
Choose exactly one value for "ticket_type":
- "Жалоба"                         — general dissatisfaction; no explicit demand for money or compensation
- "Претензия"                      — formal claim explicitly demanding compensation, refund, or cancellation ("требую", "верните деньги", "претензия", "компенсацию")
- "Смена данных"                   — request to change personal data: phone, passport, address, email
- "Консультация"                   — question or information request
- "Неработоспособность приложения" — app crash, login failure, broken feature, technical error
- "Мошеннические действия"         — fraud, unauthorized transaction, phishing, suspicious activity
- "Спам"                           — promotional offer, ad, or sales pitch unrelated to the client's account
</ticket_types>

<sentiment>
Choose exactly one value for "sentiment":
- "Позитивный" — satisfied or grateful tone
- "Нейтральный" — factual or neutral tone (always use this for Спам)
- "Негативный"  — angry, frustrated, upset tone
</sentiment>

<language>
Identify the language of the ticket text. Write the full language name in English (e.g., "Russian", "Kazakh", "English", "Uzbek", "Azerbaijani", "Tajik", etc.).

- Kazakh: Cyrillic with ә, і, ң, ғ, ү, ұ, қ, ө, һ — OR rarely Kazakh Latin recognised by Kazakh vocabulary/grammar.
- Uzbek: Latin with ʻ (oʻ, gʻ), or Cyrillic with Ҷ/Ӯ, or words like "salom", "iltimos", "ruyxat", "utolmayapman".
  Example: "Men ruyxatdan utolmayapman" → Uzbek.
- Azerbaijani: Latin with dotless ı, ə, words like "salam", "xahiş".
- English: predominantly English text.
- Russian: Russian text or any unidentified language.

Do not constrain yourself to a fixed list — name the language you actually detect.
</language>

<priority>
Integer 1–10, or null for Спам.
Base scores: Мошеннические действия=9, Претензия=8, Жалоба=6, Неработоспособность=6, Смена данных=5, Консультация=3, Спам=null.
Adjustments (cap at 10): +2 if segment is VIP or Priority (minimum result 6); +1 if sentiment is Негативный; +1 if message mentions legal action, court, account blocking, or large sum at risk.
</priority>

<output_fields>
- "summary": 1–2 sentences in Russian describing the issue (mention attachment if one was analyzed)
- "recommendation": one sentence in Russian telling the manager what to do next
</output_fields>"""


def references_attachment(description: str) -> bool:
    """Return True if the description text mentions an attachment/screenshot."""
    if not description:
        return False
    desc_lower = description.lower()
    return any(kw in desc_lower for kw in ATTACHMENT_REF_KEYWORDS)


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated for latency]"


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(kw in text for kw in keywords)


def _infer_language(description: str) -> str:
    if not description:
        return "RU"
    # Kazakh Cyrillic — highest priority; these chars appear in no other common language.
    if KZ_SPECIFIC_PATTERN.search(description):
        return "KZ"
    # Uzbek Cyrillic — Ҷ (palatal affricate) and Ӯ (oʻ) are unique to Uzbek.
    if UZ_CYRILLIC_PATTERN.search(description):
        return "RU"
    latin_count = len(LATIN_PATTERN.findall(description))
    cyr_count = len(CYRILLIC_PATTERN.findall(description))
    if latin_count >= 20 and latin_count > cyr_count:
        # Latin-dominant text — rule out Azerbaijani and Uzbek before calling it English.
        # ı (U+0131 dotless i) → Azerbaijani Latin → route as RU (no KZ/ENG skill needed).
        if AZ_LATIN_PATTERN.search(description):
            return "RU"
        # ʻ (U+02BB modifier letter turned comma, as in oʻ / gʻ) → Uzbek Latin → route as RU.
        if UZ_LATIN_PATTERN.search(description):
            return "RU"
        # Kazakh Latin (2021 alphabet) has no single unique character; the LLM handles this
        # edge case via the updated system prompt.  Fall through to ENG so the LLM can
        # override the language field with "KZ" when it recognises Kazakh Latin content.
        return "ENG"
    return "RU"


def _normalize_language(lang: str) -> str:
    """Map a free-form language name from the LLM to a routing code.

    Only "KZ" and "ENG" have special routing rules (skill requirements).
    Anything else — Russian, Uzbek, Azerbaijani, Tajik, unknown — routes as "RU"
    because all managers are assumed to speak Russian.
    """
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
        priority = None
    else:
        sentiment = _infer_sentiment(text_lower, ticket_type)
        priority = _base_priority(ticket_type)
        if (segment or "").strip().lower() in {"vip", "priority"}:
            priority = max(priority + 2, 6)
        if sentiment == "Негативный":
            priority += 1
        priority = max(1, min(10, priority))

    summary_parts = []
    if description:
        summary_parts.append(_truncate_text(description.replace("\n", " ").strip(), 180))
    else:
        summary_parts.append("Текст обращения отсутствует.")
    if attachment_context:
        summary_parts.append("Есть вложение со скриншотом.")

    recommendation_map = {
        "Спам": "Закрыть как спам и не передавать в работу менеджеру.",
        "Мошеннические действия": "Срочно эскалировать в антифрод и временно ограничить рисковые операции.",
        "Неработоспособность приложения": "Передать в техподдержку приложения и проверить логи авторизации/операций.",
        "Смена данных": "Запросить подтверждающие документы и провести обновление данных клиента.",
        "Претензия": "Передать старшему менеджеру для официального ответа и проверки оснований требований.",
        "Жалоба": "Проверить ситуацию по счету и подготовить клиенту разъяснение/решение.",
        "Консультация": "Дать клиенту инструкцию и уточнить детали запроса при необходимости.",
    }

    return {
        "ticket_type": ticket_type,
        "sentiment": sentiment,
        "priority": priority,
        "language": _infer_language(description or ""),
        "summary": " ".join(summary_parts),
        "recommendation": recommendation_map.get(ticket_type, recommendation_map["Консультация"]),
        "analysis_engine": f"heuristic:{reason}",
    }


def _try_fast_rule_based_classification(
    description: str,
    segment: str,
    attachment_context: str | None = None,
) -> dict | None:
    text = (description or "").strip()
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

    data_change_signal = _contains_any(text_lower, DATA_CHANGE_KEYWORDS)
    if data_change_signal and ("номер" in text_lower or "паспорт" in text_lower or "email" in text_lower or "адрес" in text_lower):
        return _build_heuristic_result(text, segment, "Смена данных", "data_change", attachment_context)

    if _contains_any(text_lower, APP_ISSUE_KEYWORDS):
        return _build_heuristic_result(text, segment, "Неработоспособность приложения", "app_issue", attachment_context)

    if "!" in text and _contains_any(text_lower, NEGATIVE_KEYWORDS):
        return _build_heuristic_result(text, segment, "Жалоба", "complaint", attachment_context)

    return None


# Strict JSON schema for ticket classification — gpt-5-nano enforces this at the API level,
# guaranteeing every field is present and typed correctly with no post-processing needed.
TICKET_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "ticket_classification",
        "schema": {
            "type": "object",
            "properties": {
                "ticket_type": {
                    "type": "string",
                    "enum": [
                        "Жалоба", "Претензия", "Смена данных", "Консультация",
                        "Неработоспособность приложения", "Мошеннические действия", "Спам",
                    ],
                },
                "sentiment": {
                    "type": "string",
                    "enum": ["Позитивный", "Нейтральный", "Негативный"],
                },
                "priority": {
                    "anyOf": [{"type": "integer"}, {"type": "null"}],
                },
                "language": {"type": "string"},
                "summary": {"type": "string"},
                "recommendation": {"type": "string"},
            },
            "required": ["ticket_type", "sentiment", "priority", "language", "summary", "recommendation"],
            "additionalProperties": False,
        },
    },
}

IMAGE_PROMPT = (
    "This is a screenshot attached to a customer support ticket for a brokerage app (Freedom Finance). "
    "Describe in 2-3 sentences in Russian what is shown: what screen/feature is visible, "
    "and what error or issue the screenshot demonstrates."
)

ATTACHMENTS_SUBDIR = "images"
DEFAULT_IMAGE_EXT = ".png"

# Maximum dimension (px) for the longer side of an image before sending to the model.
# OpenAI's "low detail" tile is 512×512 — anything larger adds no value at that setting.
IMAGE_MAX_SIDE_PX = 512


def _resize_image_bytes(image_path: str) -> tuple[bytes, str]:
    """
    Open an image, downscale it so its longest side ≤ IMAGE_MAX_SIDE_PX (if needed),
    and return (jpeg_bytes, mime_type).  Always re-encodes to JPEG for compactness.
    """
    from PIL import Image

    with Image.open(image_path) as img:
        img = img.convert("RGB")  # drop alpha channel; JPEG doesn't support it
        w, h = img.size
        max_side = max(w, h)
        if max_side > IMAGE_MAX_SIDE_PX:
            scale = IMAGE_MAX_SIDE_PX / max_side
            new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
            img = img.resize((new_w, new_h), Image.LANCZOS)
            print(f"[Vision] Resized {w}×{h} → {new_w}×{new_h} (scale={scale:.2f})")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue(), "image/jpeg"


def analyze_image(image_path: str) -> str:
    """
    Analyze an image attachment using gpt-5-nano vision.
    Resizes to 512px max side before encoding, then uses OpenAI's "low" detail mode
    — together these keep input token cost at ~85 tokens regardless of original size.
    Returns a Russian text description of what is shown in the screenshot.
    """
    if not os.path.exists(image_path):
        return f"[Файл вложения не найден: {os.path.basename(image_path)}]"

    img_bytes, mime = _resize_image_bytes(image_path)
    img_data = base64.standard_b64encode(img_bytes).decode("utf-8")

    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_completion_tokens=1024,  # reasoning chain + output; 300 was too tight
            reasoning_effort="minimal",  # image description needs no deep reasoning
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{img_data}", "detail": "low"},
                    },
                    {"type": "text", "text": IMAGE_PROMPT},
                ],
            }],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Ошибка анализа изображения: {e}]"


def get_attachment_context(
    attachment_filename: str | None,
    description: str | None,
    data_dir: str,
) -> str | None:
    """
    Determine and return the attachment context string for a ticket.

    Cases:
    1. Attachment file exists on disk → analyze with vision model
    2. Attachment filename given but file missing → note file not found
    3. No attachment field, but description references one → flag missing attachment
    4. No attachment, no reference → return None
    """
    if attachment_filename:
        # Preferred layout: data/images/<filename>.png
        # Keep backward compatibility with older datasets that used data/<filename>.
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


def _resolve_attachment_path(attachment_filename: str, data_dir: str) -> str | None:
    """Resolve ticket attachment to an existing file on disk."""
    raw_name = attachment_filename.strip()
    if not raw_name:
        return None

    normalized = os.path.normpath(raw_name).replace("\\", "/")
    basename = os.path.basename(normalized)
    images_dir = os.path.join(data_dir, ATTACHMENTS_SUBDIR)

    candidates: list[str] = []

    def add_candidate(path: str):
        if path not in candidates:
            candidates.append(path)

    # Safe relative path from CSV (e.g. images/foo.png).
    parts = normalized.split("/")
    if not os.path.isabs(normalized) and ".." not in parts:
        add_candidate(os.path.join(data_dir, normalized))

    # Preferred and legacy flat filename locations.
    add_candidate(os.path.join(images_dir, basename))
    add_candidate(os.path.join(data_dir, basename))

    # If extension is omitted in CSV, assume PNG by default.
    name_root, ext = os.path.splitext(basename)
    if basename and not ext:
        add_candidate(os.path.join(images_dir, f"{name_root}{DEFAULT_IMAGE_EXT}"))
        add_candidate(os.path.join(data_dir, f"{name_root}{DEFAULT_IMAGE_EXT}"))

    for path in candidates:
        if os.path.isfile(path):
            return path

    return None


def analyze_ticket(
    description: str,
    segment: str,
    country: str,
    attachment_context: str | None = None,
) -> dict:
    """Analyze a ticket and return structured attributes with latency-aware fallbacks."""
    has_text = description and description.strip()

    if not has_text and not attachment_context:
        return {
            "ticket_type": "Консультация",
            "sentiment": "Нейтральный",
            "priority": 3,
            "language": "RU",
            "summary": "Обращение без текстового описания и вложения.",
            "recommendation": "Связаться с клиентом для уточнения запроса.",
            "analysis_engine": "fallback:empty",
        }

    if ENABLE_FAST_HEURISTICS:
        heuristic = _try_fast_rule_based_classification(
            description=description or "",
            segment=segment or "Mass",
            attachment_context=attachment_context,
        )
        if heuristic is not None:
            return heuristic

    description_for_llm = _truncate_text(description or "", MAX_DESCRIPTION_CHARS)
    attachment_section = ""
    if attachment_context:
        attachment_section = f"\nAttachment context:\n{_truncate_text(attachment_context, MAX_ATTACHMENT_CTX_CHARS)}\n"

    # If there's an image but no description, raise priority slightly
    if not has_text and attachment_context:
        description_for_llm = "(Описание отсутствует — информация из вложения выше)"

    user_message = f"""Classify this support ticket. Output JSON only.

Segment: {segment or 'Mass'}
Country: {country or 'Unknown'}
Description:
{description_for_llm}
{attachment_section}"""

    try:
        request_kwargs = {
            "model": MODEL,
            "max_completion_tokens": TICKET_MAX_TOKENS,
            "response_format": TICKET_RESPONSE_FORMAT,
            "reasoning_effort": "low",   # gpt-5-nano: reasoning model; "low" balances speed vs accuracy
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        }
        if TICKET_TIMEOUT_SEC is not None:
            request_kwargs["timeout"] = TICKET_TIMEOUT_SEC

        response = client.chat.completions.create(
            **request_kwargs,
        )

        choice = response.choices[0]
        content = choice.message.content
        if not content:
            refusal = getattr(choice.message, "refusal", None)
            raise ValueError(
                f"Empty response from LLM — finish_reason={choice.finish_reason!r}, refusal={refusal!r}"
            )
        result = json.loads(content)
        result["language"] = _normalize_language(result.get("language", ""))
        result["analysis_engine"] = f"llm:{MODEL}"

    except Exception as llm_err:
        print(f"[LLM] Fast-path error: {llm_err}. Returning deterministic fallback.")
        return {
            "ticket_type": "Консультация",
            "sentiment": "Нейтральный",
            "priority": 5,
            "language": _infer_language(description or ""),
            "summary": "Ошибка LLM анализа. Требуется ручная проверка обращения.",
            "recommendation": "Провести ручную классификацию и проверить доступность LLM-сервиса.",
            "analysis_engine": "fallback:llm_error",
        }

    # Validate and sanitize required fields
    valid_types = set(TICKET_TYPES)
    valid_sentiments = {"Позитивный", "Нейтральный", "Негативный"}

    if result.get("ticket_type") not in valid_types:
        result["ticket_type"] = "Консультация"
    if result.get("sentiment") not in valid_sentiments:
        result["sentiment"] = "Нейтральный"
    if result.get("ticket_type") == "Спам":
        result["priority"] = None
        result["sentiment"] = "Нейтральный"
    elif not isinstance(result.get("priority"), int) or not 1 <= result["priority"] <= 10:
        result["priority"] = 5

    result.setdefault("analysis_engine", f"llm:{MODEL}")
    return result


def run_assistant_query(query: str, db_context: str) -> dict:
    """Run a natural language query and return chart instructions."""
    system = """You are a data analyst assistant for the FIRE ticket routing system.
You have access to a PostgreSQL database with these tables:
- tickets (id, guid, gender, birth_date, description, attachment, segment, country, region, city, street, house)
- ticket_analysis (id, ticket_id, ticket_type, sentiment, priority_score, language, summary, recommendation, attachment_description, client_lat, client_lon, nearest_office, analyzed_at)
- managers (id, full_name, position, office, skills, current_load)
- business_units (id, office_name, address, latitude, longitude)
- assignments (id, ticket_id, manager_id, assigned_office, round_robin_index, assigned_at)

Respond ONLY with valid JSON (no markdown):
{
  "answer": "brief explanation in Russian",
  "sql": "SELECT ... FROM ... GROUP BY ... ORDER BY ...",
  "chart_type": "bar|pie|line|table",
  "chart_title": "Chart title in Russian"
}

The SQL must return exactly 2 columns: label (text) and value (number)."""

    request_kwargs = {
        "model": ASSISTANT_MODEL,
        "max_completion_tokens": ASSISTANT_MAX_TOKENS,
        "response_format": {"type": "json_object"},  # assistant output is less structured; json_object is fine
        "reasoning_effort": "low",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Query: {query}\n\nData summary:\n{db_context}"},
        ],
    }
    if ASSISTANT_TIMEOUT_SEC is not None:
        request_kwargs["timeout"] = ASSISTANT_TIMEOUT_SEC

    response = client.chat.completions.create(**request_kwargs)

    content = response.choices[0].message.content or ""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "answer": content,
            "sql": None,
            "chart_type": "table",
            "chart_title": "Результат запроса",
        }
