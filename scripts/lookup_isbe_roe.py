#!/usr/bin/env python3
"""Look up Regional Office of Education for blank rows in the 2024–2025 log.

Uses the public ISBE educator inquiry that the ELIS search page calls.
A match is a person with the same first and last name whose issued PEL
includes Teacher of Students Who Are Blind or Visually Impaired.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "raw_foia" / "Teacher_Logs_2024-2025.xlsx"
RESULT = Path("/tmp/tvi_isbe_roe.json")
API = "https://apps.isbe.net/ELISAPI/api"
VI = "Teacher of Students Who Are Blind or Visually Impaired"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0",
    "Origin": "https://apps.isbe.net",
    "Referer": "https://apps.isbe.net/ELISAPP/Pages/Vue/Inquiry/EducatorSearch?inquiry=public",
}


def post(path: str, body: dict | None = None) -> object:
    data = b"" if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        API + path, data=data, headers=HEADERS, method="POST"
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=40) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code in {429, 500, 502, 503, 504} and attempt < 3:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        except urllib.error.URLError:
            if attempt < 3:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
    raise RuntimeError(path)


def blank(value: object) -> bool:
    text = "" if value is None else str(value).strip()
    return text == "" or text.upper() == "NULL"


def latest_region(registrations: list[dict]) -> str:
    issued = [
        row
        for row in registrations
        if row.get("Status") == "Issued" and row.get("Region")
    ]
    if not issued:
        return ""
    newest = max(row.get("SchoolYear") or "" for row in issued)
    regions = sorted({row["Region"] for row in issued if row.get("SchoolYear") == newest})
    return "; ".join(regions)


def has_vi(licenses: list[dict]) -> bool:
    for license_row in licenses:
        if license_row.get("CertificateCode") != "PEL":
            continue
        if license_row.get("StatusDescription") != "Issued":
            continue
        certificate_id = license_row.get("EducatorCertificateID")
        endorsements = post(
            f"/educator/educator-certificate-endorsements?educatorCertificateID={certificate_id}&inquiryType=0"
        )
        if not isinstance(endorsements, list):
            continue
        for endorsement in endorsements:
            description = endorsement.get("EndorsementGradeDescription") or ""
            if VI in description and endorsement.get("StatusDescription") == "Issued":
                return True
    return False


def lookup(first: str, last: str) -> dict:
    payload = {
        "CurrentInquiryType": 0,
        "EducatorSearchFilter": {
            "FirstName": first,
            "LastName": last,
            "RegionCode": "",
            "DistrictCode": "",
            "SiteCode": "",
            "IEIN": "",
            "BirthDate": "",
        },
    }
    found = post("/educator/educator-inquiry", payload)
    if not isinstance(found, list):
        found = []
    exact = [
        person
        for person in found
        if str(person.get("FirstName", "")).strip().casefold() == first.casefold()
        and str(person.get("LastName", "")).strip().casefold() == last.casefold()
    ]
    profiles = []
    for person in exact:
        educator_id = person["EducatorID"]
        credentials = post(
            f"/educator/educator-credentials?educatorID={educator_id}&showAll=true"
        )
        if not isinstance(credentials, dict):
            credentials = {}
        region = latest_region(credentials.get("Registrations") or [])
        vi = has_vi(credentials.get("Licenses") or [])
        profiles.append(
            {
                "id": educator_id,
                "first": str(person.get("FirstName", "")).strip(),
                "last": str(person.get("LastName", "")).strip(),
                "middle": str(person.get("MiddleInitial") or "").strip(),
                "status": person.get("Status") or "",
                "region": region,
                "vi": vi,
            }
        )
    vi_profiles = [profile for profile in profiles if profile["vi"]]
    if len(vi_profiles) == 1:
        chosen = vi_profiles[0]
        summary = chosen["region"] or "VI credential, no registered region"
    elif len(vi_profiles) > 1:
        summary = "multiple VI credentials"
    elif profiles:
        summary = "no VI credential"
    else:
        summary = "no public record"
    return {
        "first": first,
        "last": last,
        "summary": summary,
        "profiles": profiles,
    }


def main() -> None:
    workbook = load_workbook(WORKBOOK)
    sheet = workbook.active
    people = []
    for cells in sheet.iter_rows(min_row=2):
        first = "" if cells[0].value is None else str(cells[0].value).strip()
        last = "" if cells[1].value is None else str(cells[1].value).strip()
        if not first and not last:
            continue
        if not blank(cells[2].value):
            continue
        note = "" if cells[4].value is None else str(cells[4].value).strip()
        if note.startswith("Ambiguous"):
            kind = "ambiguous"
        elif note.startswith("Not a school"):
            kind = "not_a_school"
        else:
            kind = "no_record"
        people.append((kind, first, last))

    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(lookup, first, last): (kind, first, last)
            for kind, first, last in people
        }
        for future in as_completed(futures):
            kind, first, last = futures[future]
            try:
                item = future.result()
            except Exception as error:  # noqa: BLE001
                item = {
                    "first": first,
                    "last": last,
                    "summary": f"error: {error}",
                    "profiles": [],
                }
            item["kind"] = kind
            results.append(item)
            print(f"{item['summary']:28} {first} {last}", flush=True)

    results.sort(key=lambda item: (item["kind"], item["last"].casefold(), item["first"].casefold()))
    RESULT.write_text(json.dumps(results, indent=2))
    by_name = {
        (item["first"].casefold(), item["last"].casefold()): item for item in results
    }
    for cells in sheet.iter_rows(min_row=2):
        first = "" if cells[0].value is None else str(cells[0].value).strip()
        last = "" if cells[1].value is None else str(cells[1].value).strip()
        item = by_name.get((first.casefold(), last.casefold()))
        if item is None or not blank(cells[2].value):
            continue
        note = "" if cells[4].value is None else str(cells[4].value).strip()
        roe = roe_note(item)
        if "ISBE ROE:" in note:
            continue
        cells[4].value = (note + " " + roe).strip()
    workbook.save(WORKBOOK)
    print("WROTE", RESULT, "people", len(results))


def roe_note(item: dict) -> str:
    vi_profiles = [profile for profile in item["profiles"] if profile["vi"]]
    shown = vi_profiles or item["profiles"]
    if not shown:
        return "ISBE ROE: no public record."
    parts = []
    for profile in shown:
        middle = f" {profile['middle']}" if profile["middle"] else ""
        mark = "VI endorsement" if profile["vi"] else "no VI endorsement"
        region = profile["region"] or "no registered region"
        parts.append(f"{profile['first']}{middle} {profile['last']}: {region} ({mark})")
    return "ISBE ROE: " + "; ".join(parts) + "."


if __name__ == "__main__":
    main()
