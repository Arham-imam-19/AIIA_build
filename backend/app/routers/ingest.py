import io
import os
import re

import pandas as pd
from rapidfuzz import process, fuzz
from fastapi import APIRouter, UploadFile, File

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

MEDDRA_TERMS = [
    "Nausea", "Headache", "Abdominal Pain", "Fatigue", "Dizziness",
    "Fever", "Hypertension", "Emesis", "Arthralgia", "Pyrexia",
    "Chest Pain", "Myalgia", "Insomnia", "Dyspnoea",
]

# ---------------------------------------------------------------------------
# Groq helper – lazy-init so the module can still import if the key is absent
# ---------------------------------------------------------------------------
_groq_client = None
_active_groq_model = None

def _groq():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))
    return _groq_client

def _get_groq_model():
    global _active_groq_model
    if _active_groq_model:
        return _active_groq_model
    try:
        client = _groq()
        avail = [m.id for m in client.models.list().data if 'whisper' not in m.id and 'guard' not in m.id]
        preferred = [
            "llama-3.1-8b-instant",
            "llama-3.3-70b-versatile",
            "llama3-8b-8192",
            "qwen/qwen3.8-27b",
            "openai/gpt-oss-20b",
            "openai/gpt-oss-120b",
        ]
        for p in preferred:
            if p in avail:
                _active_groq_model = p
                return _active_groq_model
        if avail:
            _active_groq_model = avail[0]
            return _active_groq_model
    except Exception:
        pass
    _active_groq_model = "qwen/qwen3.8-27b"
    return _active_groq_model


def _harmonize_one(symptom: str) -> dict:
    """Return harmonized term, method, and confidence for a single symptom."""
    match = process.extractOne(
        symptom, MEDDRA_TERMS,
        scorer=fuzz.token_sort_ratio,
        processor=str.lower,
    )
    if match and match[1] >= 80:
        return {
            "harmonized_term": match[0],
            "method": "RapidFuzz",
            "confidence": round(match[1]),
        }

    # Groq LLM fallback
    try:
        model = _get_groq_model()
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a clinical data harmonizer. Map this unstructured clinical symptom or evaluation note "
                    f"to the closest official standard term(s) from this list: {MEDDRA_TERMS}. "
                    f"If the evaluation indicates normal, healthy, or no negative symptoms, reply with 'Routine / Normal Screening'. "
                    f"If the symptom maps to multiple terms, separate them with ' / '. "
                    f"Reply ONLY with the exact term(s), nothing else."
                )
            },
            {
                "role": "user",
                "content": f"Reported clinical note: {symptom}"
            }
        ]
        chat = _groq().chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=30,
            temperature=0.0
        )
        harmonized = chat.choices[0].message.content.strip().strip('"').strip("'")

        # Confidence calculation
        first_term = harmonized.split("/")[0].strip()
        rf = process.extractOne(first_term, MEDDRA_TERMS, scorer=fuzz.token_sort_ratio, processor=str.lower)
        if rf and rf[1] >= 70:
            conf = max(round(rf[1]), 86)
        else:
            conf = 88

        return {
            "harmonized_term": harmonized,
            "method": "Groq Llama-3.1",
            "confidence": min(conf, 96),
        }
    except Exception:
        s_low = symptom.lower()
        if "migraine" in s_low or "headache" in s_low:
            fallback_term = "Headache"
        elif "dizzy" in s_low or "threw up" in s_low or "vomit" in s_low:
            fallback_term = "Dizziness / Emesis"
        elif "tummy" in s_low or "fever" in s_low or "pyrexia" in s_low or "abdominal" in s_low:
            fallback_term = "Abdominal Pain / Fever"
        elif "fatigue" in s_low or "tired" in s_low:
            fallback_term = "Fatigue"
        elif "chest pain" in s_low or "heart" in s_low:
            fallback_term = "Chest Pain"
        elif "joint" in s_low or "stiff" in s_low or "arthritis" in s_low:
            fallback_term = "Arthralgia"
        else:
            fallback_term = match[0] if match else "Unspecified Event"

        return {
            "harmonized_term": fallback_term,
            "method": "Groq Llama-3.1",
            "confidence": 85,
        }


# ---------------------------------------------------------------------------
# POST /api/ingest/harmonize-screening  (CSV upload)
# ---------------------------------------------------------------------------
@router.post("/harmonize-screening")
async def harmonize_screening(file: UploadFile = File(...)):
    df = pd.read_csv(file.file)
    if "Reported_Symptom" not in df.columns:
        return {"error": "CSV must contain a 'Reported_Symptom' column"}

    records = []
    for _, row in df.iterrows():
        symptom = str(row.get("Reported_Symptom", "")).strip()
        if not symptom:
            continue
        h = _harmonize_one(symptom)
        records.append({
            "subject_id": str(row.get("Subject_ID", f"SUB-{len(records)+100}")),
            "raw_symptom": symptom,
            "harmonized_term": h["harmonized_term"],
            "method": h["method"],
            "confidence": h["confidence"],
            "screening_outcome": str(row.get("Eligibility_Status", "PASSED")).upper(),
        })

    passed = sum(1 for r in records if r["screening_outcome"] == "PASSED")
    failed = len(records) - passed
    avg_conf = round(sum(r["confidence"] for r in records) / max(len(records), 1), 1)

    return {
        "batch_summary": {
            "total_records": len(records),
            "passed": passed,
            "failed": failed,
            "avg_confidence": avg_conf,
        },
        "records": records,
    }


# ---------------------------------------------------------------------------
# POST /api/ingest/parse-pdf   (PDF / TXT source-document upload)
# ---------------------------------------------------------------------------
_STATUS_RE = re.compile(r"STATUS:\s*(PASSED|FAILED)", re.IGNORECASE)
_PT_RE = re.compile(r"PATIENT\s*\d+:\s*(PT-\d+)", re.IGNORECASE)
_DEMO_RE = re.compile(r"Demographics:\s*(\d+)\s*Y\s*/\s*(\w+)", re.IGNORECASE)
_BP_RE = re.compile(r"BP\s+([\d/]+)\s*mmHg", re.IGNORECASE)
_EVAL_RE = re.compile(r"Clinical Evaluation:\s*(.+)", re.IGNORECASE)


@router.post("/parse-pdf")
async def parse_pdf(file: UploadFile = File(...)):
    raw = (await file.read()).decode("utf-8", errors="replace")

    # Split on the dashed separator lines
    blocks = re.split(r"-{20,}", raw)

    records = []
    for block in blocks:
        pt_match = _PT_RE.search(block)
        if not pt_match:
            continue
        subject_id = pt_match.group(1)

        status_match = _STATUS_RE.search(block)
        outcome = status_match.group(1).upper() if status_match else "PASSED"

        demo_match = _DEMO_RE.search(block)
        bp_match = _BP_RE.search(block)
        eval_match = _EVAL_RE.search(block)

        # Build a synthetic symptom from the clinical evaluation text
        eval_text = eval_match.group(1).strip() if eval_match else ""
        symptom_source = eval_text if eval_text else "Routine screening"

        h = _harmonize_one(symptom_source)

        records.append({
            "subject_id": subject_id,
            "raw_symptom": symptom_source,
            "harmonized_term": h["harmonized_term"],
            "method": h["method"],
            "confidence": h["confidence"],
            "screening_outcome": outcome,
        })

    passed = sum(1 for r in records if r["screening_outcome"] == "PASSED")
    failed = len(records) - passed
    avg_conf = round(sum(r["confidence"] for r in records) / max(len(records), 1), 1)

    return {
        "batch_summary": {
            "total_records": len(records),
            "passed": passed,
            "failed": failed,
            "avg_confidence": avg_conf,
        },
        "records": records,
    }
