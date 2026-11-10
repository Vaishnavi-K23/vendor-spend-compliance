"""Field schemas, prompts and passage selection for the LLM extraction.

Bump PROMPT_VERSION whenever a prompt, schema or passage rule changes; results
are stored per version so the evaluation can show which change moved accuracy.
Change log: docs/llm-prompt-log.md.
"""
import re

PROMPT_VERSION = "v4"


def _field(value_type: str, description: str) -> dict:
    """A value plus the exact text it came from. The quote is what makes the value checkable.

    No maxLength: in v2 it distorted Ollama's grammar-constrained decoding (contract numbers came
    back as "strconv7871" or blank). Runaway quotes are handled by the output-token cap and a retry.
    """
    return {
        "type": "object",
        "properties": {
            "value": {"type": [value_type, "null"], "description": description},
            "quote": {"type": ["string", "null"], "description": "exact text copied from the document"},
        },
        "required": ["value", "quote"],
    }


# ---------- Summary fields: page 1 is a standard City form ----------

SUMMARY_FIELDS = {
    "contract_number": _field("string", "Contract (PO) Number"),
    "revision_number": _field("string", "the value after 'Modification Revision Number'; null on an original contract"),
    "contractor_name": _field("string", "Name of Contractor; on grant forms, the Delegate Agency"),
    "department": _field("string", "City Department"),
    "start_date": _field("string", "term start date as YYYY-MM-DD"),
    "end_date": _field("string", "term end date as YYYY-MM-DD"),
    "award_amount": _field("number", "Dollar Amount of Contract or Maximum Compensation, as a number; null if not stated"),
    "modification_reason": _field("string", "the Mod Reason code only, e.g. TIME EXTENSION; null on an original contract"),
}

SUMMARY_SCHEMA = {"type": "object", "properties": SUMMARY_FIELDS, "required": list(SUMMARY_FIELDS)}

SUMMARY_PROMPT = """You read the first page of a City of Chicago contract document. It is usually a
"Contract Summary Sheet" or a "Modification Summary Report". The text may come from OCR and
labels may be separated from their values.

Fill every field. Rules:
- Use only what this page says. If a field isn't on the page, value and quote are null.
- quote: copy the exact text the value came from (label and value), at most 200 characters.
- Dates: convert to YYYY-MM-DD. If OCR mangled a date and you can't read it with confidence, use null.
- award_amount: a plain number without $ or commas.
- contractor_name: the "Name of Contractor". On delegate agency grant forms it is the Delegate Agency.
- modification_reason: the short reason code only (e.g. TIME EXTENSION, SCOPE CHANGE), not the description.

Page 1:
<<<
{text}
>>>"""


# ---------- Contract-body fields: terms that exist only in the PDF ----------

BODY_FIELDS = {
    "renewal_options_count": _field(
        "integer", "number of optional renewal/extension periods the City may exercise; 0 only if the text says there are none"),
    "renewal_term_months": _field("integer", "length of each renewal/extension option in months"),
    "not_to_exceed_amount": _field(
        "number", "not-to-exceed or maximum compensation amount for the whole contract, as a number"),
    "payment_terms_days": _field("integer", "days the City has to pay an invoice, e.g. 30 or 60"),
}

BODY_SCHEMA = {"type": "object", "properties": {
    **{k: {**v, "properties": {**v["properties"], "page": {"type": ["integer", "null"]}},
           "required": ["value", "quote", "page"]} for k, v in BODY_FIELDS.items()}},
    "required": list(BODY_FIELDS)}

BODY_PROMPT = """You read excerpts from a City of Chicago contract. Each excerpt starts with its page
number, like [page 12]. The excerpts were selected by keyword, so many are irrelevant.

Extract these terms for THIS contract:
- renewal_options_count: how many optional renewal or extension periods the City may exercise
  (e.g. "two (2) additional one-year options" -> 2).
- renewal_term_months: length of each option in months (one year -> 12).
- not_to_exceed_amount: the not-to-exceed / maximum compensation for the contract, in dollars.
  Percentages ("not to exceed 12%") and per-item or hourly caps are not this field.
- payment_terms_days: days the City has to pay a proper invoice.

Rules:
- Use only the excerpts. If a term isn't stated, value, quote and page are null. Don't guess.
- Ignore generic boilerplate that describes other agreements or statutes.
- quote: copy the exact sentence the value came from, at most 300 characters. page: the excerpt's page number.

Excerpts:
<<<
{text}
>>>"""

KEYWORDS = re.compile(
    r"renew|option to extend|extension option|additional (?:\w+[- ])?(?:year|month|period)s?\b|"
    r"not[- ]to[- ]exceed|\bNTE\b|maximum compensation|"
    r"payment terms|net\s*\d{2}\b|within\s+\w+\s*\(?\d*\)?\s+days\s+(?:of|after)\s+(?:receipt|the city)",
    re.I)
WINDOW = 450          # characters kept on each side of a keyword hit
MAX_PASSAGE_CHARS = 7000


def select_passages(pages: list[dict]) -> str:
    """Keyword windows from every page, merged, densest first, capped to fit a small model's context."""
    chunks = []
    for p in pages:
        text = re.sub(r"\s+", " ", p["text"])
        spans = []
        for m in KEYWORDS.finditer(text):
            s, e = max(0, m.start() - WINDOW), min(len(text), m.end() + WINDOW)
            if spans and s <= spans[-1][1]:
                spans[-1][1] = e
                spans[-1][2] += 1
            else:
                spans.append([s, e, 1])
        chunks += [(hits, p["page"], text[s:e]) for s, e, hits in spans]
    chunks.sort(key=lambda c: -c[0])
    out, used = [], 0
    for _, page, text in chunks:
        if used + len(text) > MAX_PASSAGE_CHARS:
            continue
        out.append((page, text))
        used += len(text)
    out.sort()  # back to document order so the model reads it naturally
    return "\n\n".join(f"[page {page}] {text}" for page, text in out)
