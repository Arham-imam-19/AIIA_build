# CDISC SDTM / CDASH Standard Data Dictionary & DPDP Act PII Rules

# PII columns to completely drop according to the DPDP Act 2023.
DPDP_DROP = [
    "name", "first_name", "last_name", "full_name", 
    "phone", "phone_number", "mobile", "contact",
    "address", "street", "city", "state", "zip",
    "aadhaar", "ssn", "national_id", "email"
]

# Standard CDISC SDTM mapping rules for rapidfuzz matching.
CDISC_MAPPINGS = {
    "Subject": {
        # DM Domain (Demographics)
        "DM.USUBJID": ["subject_code", "sub_id", "participant_id", "usubjid", "id", "pt_id"],
        "DM.AGE": ["age_at_enrollment", "age", "years_old", "pt_age_yrs"],
        "DM.SEX": ["sex", "gender"],
        "DM.WEIGHT": ["weight_kg", "weight", "wt"],
        "DM.HEIGHT": ["height_cm", "height", "ht"],
        "DM.ARM": ["arm", "study_arm", "treatment_group"],
        
        # Supplemental Qualifiers (SUPPQUAL) - Ayurveda specifics
        "SUPPQUAL.PRAKRITI": ["prakriti", "body_type", "dosha_type"],
        "SUPPQUAL.DOSHA": ["dosha", "imbalance"],
        "SUPPQUAL.AGNI": ["agni", "digestive_fire"]
    },
    "AdverseEvent": {
        # AE Domain (Adverse Events)
        "AE.AETERM": ["term_verbatim", "symptom", "side_effect", "aeterm", "event"],
        "AE.AESEV": ["severity", "aesev", "intensity"],
        "AE.AESTDAT": ["onset_date", "start_date", "aestdat"]
    }
}
