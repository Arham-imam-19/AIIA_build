"""CDISC SDTM targets and mapping rules for Phase 3 Data Harmonization."""

from typing import Dict, List

# Core target dictionary mapping SDTM standard keys to aliases
SDTM_TARGETS: Dict[str, List[str]] = {
    # Demographics (DM)
    "DM.USUBJID": ["pt_id", "patient_id", "subjid", "subject_code", "pid", "record_no", "reg_no", "subject_id", "id"],
    "DM.AGE": ["age", "pt_age", "age_yrs", "years_old", "patient_age", "age_at_enrollment"],
    "DM.BRTHDTC": ["dob", "birth_date", "birthdate", "date_of_birth", "born_on", "year_of_birth"],
    "DM.SEX": ["gender", "sex", "pt_gender", "patient_sex"],
    
    # Adverse Events (AE)
    "AE.AETERM": ["adverse_event", "side_effect", "symptom", "side_fx", "reaction", "complaint", "observed_reaction"],
    "AE.AESEV": ["severity", "ae_grade", "intensity", "how_severe", "reaction_severity", "severity_grade"],
    
    # Vital Signs (VS)
    "VS.SYSBP": ["sbp", "sys_bp", "systolic", "bp_sys", "sbp_value", "systolic_bp"],
    "VS.DIABP": ["dbp", "dia_bp", "diastolic", "bp_dia", "dbp_value", "diastolic_bp"],
    
    # Study Arm
    "DM.ARM": ["arm", "treatment_arm", "group", "study_group", "cohort"],
}

# DPDP Act 2023 - Data Minimization patterns (Direct Identifiers to DROP)
PII_PATTERNS: List[str] = [
    "phone", "mobile", "contact_no", "contact_phone", "contact_phone_num", 
    "aadhaar", "address", "home_address", "residential_address", 
    "guardian_name", "first_name", "last_name", "full_name", 
    "patient_name", "name", "email"
]

# Supplemental Metadata (Ayurveda specific patterns mapped to suppqual)
AYURVEDA_SUPPLEMENTAL: List[str] = [
    "prakriti", "prakriti_dominant", "dosha", "agni", "agni_type", 
    "koshta", "ayush_code", "diet_compliance", "dosha_score"
]
