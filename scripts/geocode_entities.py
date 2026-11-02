"""Match employer offices and school buildings to public coordinates.

School districts and cooperatives come from the NCES EDGE 2023–24 location
files. A few campuses are not school districts. Those use a published street
address and the Census geocoder. Nothing in this script invents a latitude.
"""

from __future__ import annotations

import csv
import io
import re
import sys
import urllib.parse
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.downloads import download, fetch_json
from scripts.sources import load_coms, load_current, load_prior
from scripts.tvi_data import (
    NCES_SOURCE,
    county_key,
    district_numbers,
    expand_name,
    in_illinois,
    load_overrides,
    load_roes,
    match_employer,
    match_school,
    plan_people,
    write_json,
    lea_kind,
)

LEA_QUERY = (
    "https://nces.ed.gov/opengis/rest/services/K12_School_Locations/"
    "EDGE_GEOCODE_PUBLICLEA_2324/MapServer/0/query"
)
SCHOOL_QUERY = (
    "https://nces.ed.gov/opengis/rest/services/K12_School_Locations/"
    "EDGE_GEOCODE_PUBLICSCH_2324/MapServer/0/query"
)
CENSUS_GEOCODER = (
    "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
)

IPEDS_URL = "https://nces.ed.gov/ipeds/datacenter/data/HD2024.zip"
IPEDS_PAGE = "https://nces.ed.gov/ipeds/datacenter/DataFiles.aspx"
# Employer name, after expand_name, to the IPEDS institution name.
IPEDS_MATCH = {
    "illinois state university": "illinois state university",
    "northern illinois university": "northern illinois university",
    "university of illinois at urbana champaign": "university of illinois urbana-champaign",
}
# Street addresses published by the state facilities. Coordinates come from Census.
CAMPUSES = [
    {
        "match": "illinois school for the visually impaired",
        "address": "658 E State St, Jacksonville, IL 62650",
        "city": "jacksonville",
        "source_url": "https://www.dhs.state.il.us/page.aspx?item=87427",
    },
    {
        "match": "illinois center for rehabilitation and education wood",
        "address": "1151 S Wood St, Chicago, IL 60612",
        "city": "chicago",
        "source_url": "https://www.dhs.state.il.us/page.aspx?item=32297",
    },
]


def query_features(url: str, out_fields: str, order_field: str) -> list[dict[str, object]]:
    features: list[dict[str, object]] = []
    offset = 0
    while offset < 20000:
        params = urllib.parse.urlencode(
            {
                "where": "STATE='IL'",
                "outFields": out_fields,
                "returnGeometry": "false",
                "orderByFields": order_field,
                "resultOffset": str(offset),
                "resultRecordCount": "2000",
                "f": "json",
            }
        )
        payload = fetch_json(f"{url}?{params}")
        if payload.get("error"):
            raise RuntimeError(f"NCES query failed: {payload['error']}")
        batch = payload.get("features")
        if not isinstance(batch, list) or not batch:
            break
        features.extend(item for item in batch if isinstance(item, dict))
        offset += len(batch)
        if len(batch) < 2000 and not payload.get("exceededTransferLimit"):
            break
    return features


def _attributes(feature: dict[str, object]) -> dict[str, object]:
    attributes = feature.get("attributes")
    if isinstance(attributes, dict):
        return attributes
    return {}


def _address(attributes: dict[str, object]) -> str:
    street = str(attributes.get("STREET") or "").strip()
    city = str(attributes.get("CITY") or "").strip()
    state = str(attributes.get("STATE") or "").strip()
    zip_code = str(attributes.get("ZIP") or "").strip()
    place = ", ".join(part for part in (street, city) if part)
    region = " ".join(part for part in (state, zip_code) if part)
    return ", ".join(part for part in (place, region) if part)


def load_leas() -> list[dict[str, object]]:
    features = query_features(
        LEA_QUERY,
        "LEAID,NAME,STREET,CITY,STATE,ZIP,NMCNTY,LAT,LON",
        "LEAID",
    )
    leas = []
    for feature in features:
        attributes = _attributes(feature)
        name = str(attributes.get("NAME") or "").strip()
        lat = attributes.get("LAT")
        lng = attributes.get("LON")
        if not name or not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
            continue
        if not in_illinois(float(lat), float(lng)):
            continue
        expanded = expand_name(name)
        leas.append(
            {
                "leaid": str(attributes.get("LEAID") or ""),
                "name": name,
                "expanded": expanded,
                "county": county_key(str(attributes.get("NMCNTY") or "")),
                "city": county_key(str(attributes.get("CITY") or "")),
                "lat": float(lat),
                "lng": float(lng),
                "address": _address(attributes),
                "numbers": district_numbers(expanded),
            }
        )
    return leas


def load_schools() -> dict[str, list[dict[str, object]]]:
    features = query_features(
        SCHOOL_QUERY,
        "NCESSCH,LEAID,NAME,STREET,CITY,STATE,ZIP,NMCNTY,LAT,LON",
        "NCESSCH",
    )
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for feature in features:
        attributes = _attributes(feature)
        name = str(attributes.get("NAME") or "").strip()
        leaid = str(attributes.get("LEAID") or "")
        lat = attributes.get("LAT")
        lng = attributes.get("LON")
        if not name or not leaid or not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
            continue
        if not in_illinois(float(lat), float(lng)):
            continue
        grouped[leaid].append(
            {
                "ncessch": str(attributes.get("NCESSCH") or ""),
                "leaid": leaid,
                "name": name,
                "expanded": expand_name(name),
                "county": county_key(str(attributes.get("NMCNTY") or "")),
                "lat": float(lat),
                "lng": float(lng),
                "address": _address(attributes),
            }
        )
    return grouped


def address_agrees(query: str, matched: str) -> bool:
    """Reject a Census match that keeps the number but flips the street side."""
    query_text = re.sub(r"[^a-z0-9]+", " ", query.casefold()).strip()
    matched_text = re.sub(r"[^a-z0-9]+", " ", matched.casefold()).strip()
    leading = re.match(r"(\d+)\s+([nsew])\b", query_text)
    if leading:
        number, direction = leading.group(1), leading.group(2)
        return f"{number} {direction} " in f"{matched_text} "
    number = re.match(r"(\d+)\b", query_text)
    if not number:
        return False
    return number.group(1) in matched_text.split(" ")


def load_ipeds(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        download(IPEDS_URL, path)
    with zipfile.ZipFile(path) as archive:
        name = next(item for item in archive.namelist() if item.lower().endswith(".csv"))
        text = archive.read(name).decode("utf-8-sig")
    institutions: dict[str, dict[str, object]] = {}
    for row in csv.DictReader(io.StringIO(text)):
        if row.get("STABBR") != "IL":
            continue
        institution = (row.get("INSTNM") or "").strip()
        try:
            lat = float(row.get("LATITUDE") or "")
            lng = float(row.get("LONGITUD") or "")
        except ValueError:
            continue
        if not institution or not in_illinois(lat, lng):
            continue
        address = ", ".join(
            part
            for part in (
                (row.get("ADDR") or "").strip(),
                (row.get("CITY") or "").strip(),
                " ".join(part for part in ((row.get("STABBR") or "").strip(), (row.get("ZIP") or "").strip()) if part),
            )
            if part
        )
        institutions[institution.casefold()] = {
            "name": institution,
            "lat": lat,
            "lng": lng,
            "address": address,
        }
    return institutions


def census_point(address: str, city: str) -> tuple[float, float, str] | None:
    params = urllib.parse.urlencode(
        {"address": address, "benchmark": "Public_AR_Current", "format": "json"}
    )
    payload = fetch_json(f"{CENSUS_GEOCODER}?{params}")
    result = payload.get("result")
    matches = result.get("addressMatches") if isinstance(result, dict) else None
    if not isinstance(matches, list):
        return None
    for match in matches:
        if not isinstance(match, dict):
            continue
        components = match.get("addressComponents")
        component_city = ""
        state = ""
        if isinstance(components, dict):
            component_city = str(components.get("city") or "")
            state = str(components.get("state") or "")
        matched = str(match.get("matchedAddress") or "")
        if state and state.upper() != "IL":
            continue
        city_ok = component_city.casefold() == city.casefold() or f", {city.casefold()}," in matched.casefold()
        if not city_ok or not address_agrees(address, matched):
            continue
        coordinates = match.get("coordinates")
        if not isinstance(coordinates, dict):
            continue
        lng = coordinates.get("x")
        lat = coordinates.get("y")
        if not isinstance(lat, (int, float)) or not isinstance(lng, (int, float)):
            continue
        if not in_illinois(float(lat), float(lng)):
            continue
        return float(lat), float(lng), matched
    return None


def _cache_record(
    kind: str,
    lat: float,
    lng: float,
    address: str,
    source_url: str,
    matched_name: str,
    county: str,
    leaid: str = "",
) -> dict[str, object]:
    return {
        "kind": kind,
        "lat": lat,
        "lng": lng,
        "address": address,
        "source_url": source_url,
        "matched_name": matched_name,
        "county": county,
        "leaid": leaid,
    }


def main() -> None:
    raw = ROOT / "raw_foia"
    roes = load_roes(raw / "illinois_roe_and_county_directory.md")
    people = plan_people(
        load_current(raw / "Teacher_Logs_2024-2025.xlsx"),
        load_prior(raw / "Teacher_Logs_2023-2024.xlsx"),
        load_coms(raw / "Illinois_COMS_govsalaries.xlsx"),
        roes,
        load_overrides(ROOT / "data" / "overrides.json"),
    )
    print("Downloading Illinois district and school locations from NCES...")
    ipeds = load_ipeds(ROOT / "data" / "source" / "HD2024.zip")
    leas = load_leas()
    schools = load_schools()
    print(f"district offices in Illinois: {len(leas)}")
    print(f"school buildings in Illinois: {sum(len(items) for items in schools.values())}")

    cache: dict[str, dict[str, object]] = {}
    employer_leas: dict[str, dict[str, object]] = {}
    exact = 0
    fuzzy: list[str] = []
    campus_misses: list[str] = []
    seen_employers: set[str] = set()

    for person in people:
        for employer in person["employers"]:  # type: ignore[union-attr]
            office_id = str(employer["office_id"])
            if office_id in seen_employers or employer["is_dhs"]:
                seen_employers.add(office_id)
                continue
            seen_employers.add(office_id)
            name = str(employer["name"])
            county = str(employer["county"])
            matched = match_employer(name, county, leas)
            if matched is not None:
                cache[office_id] = _cache_record(
                    lea_kind(str(matched["name"])),
                    float(matched["lat"]),
                    float(matched["lng"]),
                    str(matched.get("address") or ""),
                    NCES_SOURCE,
                    str(matched["name"]),
                    str(matched.get("county") or ""),
                    str(matched.get("leaid") or ""),
                )
                employer_leas[office_id] = matched
                if expand_name(name) == matched.get("expanded"):
                    exact += 1
                else:
                    fuzzy.append(f"{name} ({county}) -> {matched['name']}")
                continue
            ipeds_name = IPEDS_MATCH.get(expand_name(name))
            institution = ipeds.get(ipeds_name) if ipeds_name else None
            if institution is not None:
                cache[office_id] = _cache_record(
                    "campus",
                    float(institution["lat"]),
                    float(institution["lng"]),
                    str(institution["address"]),
                    IPEDS_PAGE,
                    str(institution["name"]),
                    county_key(county),
                )
                print(f"campus: {name} -> {institution['name']}, {institution['address']}")
                continue
            campus = next(
                (item for item in CAMPUSES if item["match"] == expand_name(name)),
                None,
            )
            if campus is None:
                continue
            point = census_point(campus["address"], campus["city"])
            if point is None:
                campus_misses.append(name)
                continue
            lat, lng, matched_address = point
            cache[office_id] = _cache_record(
                "campus",
                lat,
                lng,
                matched_address,
                campus["source_url"],
                name,
                county_key(county),
            )
            print(f"campus: {name} -> {matched_address}")

    school_hits = 0
    school_misses = 0
    seen_schools: set[str] = set()
    for person in people:
        employer_ids = [
            str(item["leaid"])
            for employer in person["employers"]  # type: ignore[union-attr]
            if not employer["is_dhs"]
            for item in [employer_leas.get(str(employer["office_id"]))]
            if item and item.get("leaid")
        ]
        for school in person["schools"]:  # type: ignore[union-attr]
            office_id = str(school["office_id"])
            if office_id in seen_schools:
                continue
            seen_schools.add(office_id)
            candidate_ids = list(employer_ids)
            district = str(school.get("district") or "")
            hint = str(school.get("county_hint") or "")
            if district:
                district_match = match_employer(district, hint, leas) if hint else None
                if district_match is None and not hint:
                    expanded = expand_name(district)
                    exact_leas = [lea for lea in leas if lea.get("expanded") == expanded]
                    if len(exact_leas) == 1:
                        district_match = exact_leas[0]
                if district_match and district_match.get("leaid"):
                    candidate_ids.append(str(district_match["leaid"]))
            pool: list[dict[str, object]] = []
            seen_pool: set[str] = set()
            for leaid in candidate_ids:
                for building in schools.get(leaid, []):
                    ncessch = str(building.get("ncessch") or "")
                    if ncessch in seen_pool:
                        continue
                    seen_pool.add(ncessch)
                    pool.append(building)
            matched_school = match_school(str(school["site"]), pool) if pool else None
            if matched_school is None:
                school_misses += 1
                print(f"  unmatched school: {school['site']} | {school.get('district') or school.get('label_employer')}")
                continue
            school_hits += 1
            if expand_name(str(school["site"])) != matched_school.get("expanded"):
                print(f"  school: {school['site']} -> {matched_school['name']}")
            cache[office_id] = _cache_record(
                "school",
                float(matched_school["lat"]),
                float(matched_school["lng"]),
                str(matched_school.get("address") or ""),
                NCES_SOURCE,
                str(matched_school["name"]),
                str(matched_school.get("county") or ""),
                str(matched_school.get("leaid") or ""),
            )

    write_json(ROOT / "data" / "geocode_cache.json", {"offices": cache})
    print(f"exact employer matches: {exact}")
    print(f"fuzzy employer matches: {len(fuzzy)}")
    for line in fuzzy:
        print(f"  fuzzy: {line}")
    print(f"school matches: {school_hits}")
    print(f"school sites left unmatched: {school_misses}")
    if campus_misses:
        print("campus geocodes that failed:")
        for name in campus_misses:
            print(f"  {name}")
    print(f"cached offices: {len(cache)}")


if __name__ == "__main__":
    main()
