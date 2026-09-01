"""Tests for CDISC SDTM Dataset-JSON v1.1 and SDTM ZIP Package Export."""

import csv
import io
import json
import zipfile
from sqlmodel import Session, select

from app.enums import UserRole
from app.models import Trial
from tests.conftest import client_for


def test_cdisc_dataset_json_export(seeded_engine):
    with Session(seeded_engine) as session:
        trial = session.exec(select(Trial)).first()
        assert trial is not None
        trial_id = trial.id
        protocol = trial.protocol_number

    sponsor_client = client_for(seeded_engine, UserRole.SPONSOR.value)

    res = sponsor_client.get(f"/api/trials/{trial_id}/export/cdisc-json")
    assert res.status_code == 200
    data = res.json()

    # 1. CDISC Dataset-JSON 1.1 Specification Verification
    assert data["datasetJSONVersion"] == "1.1.0"
    assert data["studyOID"] == protocol
    assert data["metaDataVersionOID"] == "SDTM-IG-3.3"
    assert "clinicalData" in data

    item_groups = data["clinicalData"]["itemGroupData"]
    # Check that all 5 key SDTM domains are present
    assert "DM" in item_groups
    assert "AE" in item_groups
    assert "SV" in item_groups
    assert "DV" in item_groups
    assert "TS" in item_groups

    # Validate Demographics (DM) domain structure
    dm = item_groups["DM"]
    assert dm["name"] == "DM"
    assert dm["records"] > 0
    dm_group = dm["itemGroupData"]["IG.DM"]
    item_names = [it["name"] for it in dm_group["items"]]
    assert "USUBJID" in item_names
    assert "ARM" in item_names
    assert "SEX" in item_names
    assert "COUNTRY" in item_names


def test_cdisc_sdtm_zip_package_export(seeded_engine):
    with Session(seeded_engine) as session:
        trial = session.exec(select(Trial)).first()
        assert trial is not None
        trial_id = trial.id

    regulator_client = client_for(seeded_engine, UserRole.REGULATOR.value)

    res = regulator_client.get(f"/api/trials/{trial_id}/export/cdisc-sdtm.zip")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"

    # Inspect zip contents
    zip_bytes = io.BytesIO(res.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        namelist = zf.namelist()
        assert "SDTM_DM.csv" in namelist
        assert "SDTM_AE.csv" in namelist
        assert "SDTM_SV.csv" in namelist
        assert "SDTM_DV.csv" in namelist
        assert "SDTM_TS.csv" in namelist
        assert "define.json" in namelist

        # Validate DM.csv content
        dm_csv_content = zf.read("SDTM_DM.csv").decode("utf-8")
        reader = csv.DictReader(io.StringIO(dm_csv_content))
        rows = list(reader)
        assert len(rows) > 0
        first_row = rows[0]
        assert "USUBJID" in first_row
        assert "STUDYID" in first_row
        assert first_row["COUNTRY"] == "IND"

        # Validate define.json
        define_content = json.loads(zf.read("define.json").decode("utf-8"))
        assert define_content["standard"] == "CDISC SDTM v1.7 / SDTM-IG v3.3"
        assert "DM" in define_content["domains"]
