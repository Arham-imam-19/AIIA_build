"""Algorithmic mapping engine using rapidfuzz."""

from typing import List, Dict, Any
from pydantic import BaseModel
from rapidfuzz import process, fuzz

from app.harmonization.cdisc_dictionary import SDTM_TARGETS, PII_PATTERNS, AYURVEDA_SUPPLEMENTAL

class MappingProposal(BaseModel):
    original_header: str
    suggested_target: str | None
    target_label: str
    confidence: float
    action: str  # "MAP_CORE", "MAP_SUPPLEMENTAL", "DROP_PII", "UNRESOLVED"
    sample_values: List[str]

def _clean_header(header: str) -> str:
    """Normalize headers for string matching."""
    return header.strip().lower().replace("_", " ").replace("-", " ")

def _is_high_match(cleaned_header: str, pattern_list: List[str], threshold: float = 80.0) -> bool:
    """Check if header matches any in the pattern list with a high token set ratio."""
    if not pattern_list:
        return False
    # Using extractOne to find the best match in the list
    match = process.extractOne(cleaned_header, pattern_list, scorer=fuzz.token_set_ratio)
    if match and match[1] >= threshold:
        return True
    return False

def analyze_headers(headers: List[str], sample_rows: List[Dict[str, Any]]) -> List[MappingProposal]:
    """
    Analyze raw CSV headers and propose mapping to CDISC standard or policy actions.
    """
    proposals = []
    
    for header in headers:
        cleaned = _clean_header(header)
        
        # Get first 2 non-empty values for sample
        samples = []
        for row in sample_rows:
            val = str(row.get(header, "")).strip()
            if val and val.lower() not in ["none", "null", "nan"]:
                samples.append(val)
            if len(samples) >= 2:
                break
        
        # 1. DPDP Act Check (PII Dropping)
        # Using exact substring match or high fuzz ratio for PII
        if any(pii.replace("_", " ") in cleaned for pii in PII_PATTERNS) or _is_high_match(cleaned, [p.replace("_", " ") for p in PII_PATTERNS]):
            proposals.append(MappingProposal(
                original_header=header,
                suggested_target=None,
                target_label="Drop (DPDP Minimization)",
                confidence=98.0,
                action="DROP_PII",
                sample_values=samples
            ))
            continue
            
        # 2. Ayurveda Supplemental Check
        if any(supp.replace("_", " ") in cleaned for supp in AYURVEDA_SUPPLEMENTAL) or _is_high_match(cleaned, [s.replace("_", " ") for s in AYURVEDA_SUPPLEMENTAL]):
            proposals.append(MappingProposal(
                original_header=header,
                suggested_target=f"SUPPQUAL.{cleaned.replace(' ', '_')}",
                target_label=f"Supplemental ({cleaned})",
                confidence=90.0,
                action="MAP_SUPPLEMENTAL",
                sample_values=samples
            ))
            continue
            
        # 3. CDISC SDTM Core Mapping via RapidFuzz
        best_score = 0.0
        best_target = None
        
        for sdtm_key, aliases in SDTM_TARGETS.items():
            # Clean aliases just in case
            clean_aliases = [a.replace("_", " ") for a in aliases]
            
            # token_sort_ratio is great for "patient age" vs "age patient"
            match = process.extractOne(cleaned, clean_aliases, scorer=fuzz.token_sort_ratio)
            if match:
                score = match[1]
                if score > best_score:
                    best_score = score
                    best_target = sdtm_key
                    
        # Thresholding
        if best_score >= 65.0:
            proposals.append(MappingProposal(
                original_header=header,
                suggested_target=best_target,
                target_label=best_target,
                confidence=round(best_score, 1),
                action="MAP_CORE",
                sample_values=samples
            ))
        else:
            proposals.append(MappingProposal(
                original_header=header,
                suggested_target=None,
                target_label="Unmapped / Ignore",
                confidence=round(best_score, 1),
                action="UNRESOLVED",
                sample_values=samples
            ))
            
    return proposals
