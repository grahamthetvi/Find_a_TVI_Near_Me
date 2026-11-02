"""Pure functions for the Illinois TVI directory build.

Names, ROE labels, employer and school matching, and the records the
static page reads. Network access and workbooks stay in the scripts.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

COOK_CODES = {"05", "06", "07", "15"}
COOK_LABELS = {
    "05": "North Cook",
    "06": "West Cook",
    "07": "South Cook",
    "15": "City of Chicago",
}
NON_REGIONS = {
    "not found",
    "error",
    "credential verified region missing",
}
COUNTY_ABBREVIATIONS = {
    "clk": "clark",
    "cls": "coles",
    "cmbn": "cumberland",
    "dglas": "douglas",
    "edgr": "edgar",
    "mltr": "moultrie",
    "shlb": "shelby",
    "cwford": "crawford",
    "jsper": "jasper",
    "lwrnce": "lawrence",
    "rhland": "richland",
}
ABBREVIATIONS = {
    "cooprtv": "cooperative",
    "educl": "educational",
    "ccsd": "community consolidated school district",
    "cusd": "community unit school district",
    "chsd": "community high school district",
    "hsd": "high school district",
    "esd": "elementary school district",
    "psd": "public school district",
    "csd": "community school district",
    "cud": "community unit district",
    "assn": "association",
    "assoc": "association",
    "cntys": "counties",
    "cnty": "county",
    "dists": "districts",
    "dist": "district",
    "comm": "community",
    "cons": "consolidated",
    "spec": "special",
    "educ": "education",
    "elem": "elementary",
    "coop": "cooperative",
    "twp": "township",
    "dept": "department",
    "jnt": "joint",
    "agr": "agreement",
    "org": "organization",
    "ctr": "center",
    "sch": "school",
    "ud": "unit district",
    "sd": "school district",
    "co": "county",
    "ed": "education",
    "il": "illinois",
    "hs": "high school",
    "jr": "junior",
    "sr": "senior",
    "sp": "special",
    "st": "saint",
    "mt": "mount",
    "nw": "northwest",
}
CONTENT_STOPWORDS = {"of", "the", "and", "for", "a", "in"}
GENERIC_TOKENS = CONTENT_STOPWORDS | {
    "school",
    "schools",
    "district",
    "districts",
    "community",
    "unit",
    "consolidated",
    "county",
    "counties",
    "public",
    "illinois",
    "area",
    "special",
    "education",
    "educational",
    "cooperative",
    "association",
    "department",
    "center",
    "high",
    "elementary",
    "township",
    "joint",
    "agreement",
    "services",
    "organization",
    "senior",
    "junior",
    "primary",
    "middle",
}
NCES_SOURCE = "https://nces.ed.gov/programs/edge/geographic/schoollocations"
EARTH_RADIUS_MILES = 3958.7613
SAME_BUILDING_MILES = 0.2
YEAR_PRIOR = "2023-2024"
YEAR_CURRENT = "2024-2025"
SCHOOL_YEARS = (YEAR_PRIOR, YEAR_CURRENT)
ROLE_ORDER = ("TVI", "COMS", "CATIS", "CLVT", "CVRT")
EMPTY_VALUES = {"", "null", "na", "none", "n/a"}
BRACKET_NOTE = re.compile(r"\s*\[[^\]]*\]\s*")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")


def fold_space(value: str) -> str:
    text = (value or "").casefold().replace("&", " and ").replace(".", " ")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("du page", "dupage")
    text = text.replace("de kalb", "dekalb")
    text = text.replace("de witt", "dewitt")
    text = text.replace("la salle", "lasalle")
    text = text.replace("la grange", "lagrange")
    text = text.replace("saint clair", "st clair")
    text = re.sub(r"\bmc\s+", "mc", text)
    return re.sub(r"\s+", " ", text).strip()


def expand_name(value: str) -> str:
    tokens: list[str] = []
    for token in fold_space(value).split(" "):
        if not token:
            continue
        replacement = ABBREVIATIONS.get(token)
        if replacement:
            tokens.extend(replacement.split(" "))
        else:
            tokens.append(token)
    return " ".join(tokens)


def county_key(value: str) -> str:
    text = fold_space(value)
    text = re.sub(r"\s+count(?:y|ies)$", "", text)
    return text.strip()


def bare_place_name(value: str) -> str:
    return re.sub(
        r"\s+(city|village|town|cdp|borough)$",
        "",
        (value or "").strip(),
        flags=re.IGNORECASE,
    )


def place_key(value: str) -> str:
    text = fold_space(bare_place_name(value))
    text = re.sub(r"\bst\b", "saint", text)
    text = re.sub(r"\bmt\b", "mount", text)
    text = re.sub(r"\s+(illinois|il)$", "", text)
    return text.strip()


def slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", fold_space(value)).strip("-")
    return text or "unknown"


def name_key(first: str, last: str) -> tuple[str, str]:
    def part(value: str) -> str:
        return re.sub(r"\s+", " ", (value or "").strip()).casefold()

    return (part(first), part(last))


def _cap_token(token: str) -> str:
    if "-" in token:
        return "-".join(_cap_token(piece) for piece in token.split("-"))
    if "'" in token:
        return "'".join(piece.capitalize() for piece in token.split("'"))
    lower = token.casefold()
    if lower.startswith("mc") and len(lower) > 2:
        return "Mc" + lower[2:].capitalize()
    return lower.capitalize()


def display_name(first: str, last: str) -> str:
    def fix(value: str) -> str:
        text = re.sub(r"\s+", " ", (value or "").strip())
        if text.isupper():
            return " ".join(_cap_token(token) for token in text.split(" "))
        return text

    return f"{fix(first)} {fix(last)}".strip()


def clean_label(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def clean_source_label(value: str) -> str:
    return clean_label(BRACKET_NOTE.sub(" ", value or ""))


def has_value(value: str) -> bool:
    return clean_label(value).casefold() not in EMPTY_VALUES


def ordered_roles(roles: set[str]) -> list[str]:
    return [role for role in ROLE_ORDER if role in roles]


def content_tokens(expanded: str) -> set[str]:
    return {token for token in expanded.split(" ") if token and token not in CONTENT_STOPWORDS}


def distinctive_words(expanded: str) -> set[str]:
    words = set()
    for token in content_tokens(expanded):
        if token in GENERIC_TOKENS or re.fullmatch(r"\d+[a-z]?", token):
            continue
        words.add(token)
    return words


def district_numbers(expanded: str) -> frozenset[str]:
    return frozenset(re.findall(r"\b\d{1,4}[a-z]?\b", expanded))


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)
    half = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * math.asin(min(1.0, math.sqrt(half)))


def in_illinois(lat: float | None, lng: float | None) -> bool:
    if lat is None or lng is None:
        return False
    return 36.95 <= lat <= 42.52 and -91.52 <= lng <= -87.49


def is_cps(name: str) -> bool:
    expanded = expand_name(name)
    return "chicago public schools" in expanded and "299" in expanded.split(" ")


def is_dhs(name: str) -> bool:
    expanded = expand_name(name)
    if expanded.startswith("illinois "):
        expanded = expanded[len("illinois ") :]
    return expanded == "department of human services" or expanded.startswith(
        "department of human services "
    )


def employer_office_id(name: str, county: str) -> str:
    return f"employer-{slug(name)}-{slug(county)}"


def school_office_id(district: str, site: str) -> str:
    return f"school-{slug(district)}-{slug(site)}"


def location_label(employer: str, detail: str | None, roe: str | None) -> str:
    if detail == "district office":
        head = f"{employer}, district office"
    elif detail:
        head = f"{detail}, {employer}"
    else:
        head = employer
    if roe:
        return f"{head}, {roe}"
    return head


def counties_from_note(note: str) -> list[str]:
    match = re.search(r"Official ISBE jurisdiction:\s*(.+)", note or "")
    if not match:
        return []
    body = match.group(1).strip().rstrip(".")
    body = re.sub(r"\s+Counties$", "", body, flags=re.IGNORECASE)
    body = re.sub(r"\s+County$", "", body, flags=re.IGNORECASE)
    return [part.strip() for part in body.split(",") if part.strip()]


def roe_label(code: str, counties: list[str]) -> str | None:
    if code in COOK_LABELS:
        return COOK_LABELS[code]
    if not counties:
        return None
    if len(counties) == 1:
        return f"{counties[0]} ROE"
    if len(counties) == 2:
        return f"{counties[0]} and {counties[1]} ROE"
    return f"{', '.join(counties[:-1])}, and {counties[-1]} ROE"


def load_roes(path: Path) -> list[dict[str, object]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    roes: list[dict[str, object]] = []
    for row in raw:
        code = str(row["roe_code"])
        counties = [str(county) for county in row.get("counties") or []]
        if not counties and row.get("note"):
            counties = counties_from_note(str(row["note"]))
        if code in COOK_CODES:
            counties = ["Cook"]
        roes.append(
            {
                "roe_code": code,
                "type": row.get("type") or "",
                "label": roe_label(code, counties),
                "counties": counties,
            }
        )
    roes.sort(key=lambda item: str(item["roe_code"]))
    return roes


def _roe_indexes(
    roes: list[dict[str, object]],
) -> tuple[dict[str, dict[str, object]], dict[str, set[str]], dict[frozenset[str], list[str]]]:
    by_code = {str(roe["roe_code"]): roe for roe in roes}
    by_county: dict[str, set[str]] = {}
    by_set: dict[frozenset[str], list[str]] = {}
    for roe in roes:
        code = str(roe["roe_code"])
        if code in COOK_CODES or code == "60":
            continue
        keys = [county_key(str(county)) for county in roe["counties"]]  # type: ignore[union-attr]
        if not keys:
            continue
        for key in keys:
            by_county.setdefault(key, set()).add(code)
        by_set.setdefault(frozenset(keys), []).append(code)
    return by_code, by_county, by_set


def region_code(region: str, roes: list[dict[str, object]]) -> str | None:
    text = (region or "").casefold().replace("&", " and ").replace(".", " ")
    text = re.sub(r"[^a-z0-9/]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\broe$", "", text).strip()
    if not text or text in NON_REGIONS or text.startswith("credential verified"):
        return None
    if "city of chicago" in text:
        return "15"
    numbered = re.search(r"\bregion\s+0?([567])\b", text)
    if numbered:
        return f"0{numbered.group(1)}"
    parts: list[str] = []
    for part in text.split("/"):
        token = part.strip()
        if not token:
            continue
        compact = token.replace(" ", "")
        if compact in COUNTY_ABBREVIATIONS:
            parts.append(COUNTY_ABBREVIATIONS[compact])
        else:
            parts.append(county_key(token))
    _by_code, _by_county, by_set = _roe_indexes(roes)
    matches = by_set.get(frozenset(parts), [])
    if len(matches) == 1:
        return matches[0]
    return None


def label_for_code(code: str | None, roes: list[dict[str, object]]) -> str | None:
    if not code:
        return None
    for roe in roes:
        if roe["roe_code"] == code:
            label = roe["label"]
            return str(label) if label else None
    return None


def employer_roe_label(
    county: str,
    employer: str,
    prior_regions: list[str],
    roes: list[dict[str, object]],
) -> str | None:
    if is_cps(employer):
        return label_for_code("15", roes)
    _by_code, by_county, _by_set = _roe_indexes(roes)
    if county_key(county) == "cook":
        cook_codes = []
        for region in prior_regions:
            code = region_code(region, roes)
            if code in COOK_CODES:
                cook_codes.append(code)
        unique = set(cook_codes)
        if len(unique) == 1:
            return label_for_code(cook_codes[0], roes)
        return None
    matches = by_county.get(county_key(county), set())
    if len(matches) == 1:
        return label_for_code(next(iter(matches)), roes)
    return None


def region_county_hint(region: str, roes: list[dict[str, object]]) -> str | None:
    code = region_code(region, roes)
    if not code:
        return None
    if code in COOK_CODES:
        return "cook"
    for roe in roes:
        if roe["roe_code"] != code:
            continue
        counties = roe["counties"]
        if isinstance(counties, list) and len(counties) == 1:
            return county_key(str(counties[0]))
    return None


def _prefer_raw_name(
    current: tuple[str, str] | None, candidate: tuple[str, str]
) -> tuple[str, str]:
    if current is None:
        return candidate
    current_raw = f"{current[0]} {current[1]}"
    candidate_raw = f"{candidate[0]} {candidate[1]}"
    if current_raw.isupper() and not candidate_raw.isupper():
        return candidate
    return current


def empty_overrides() -> dict[str, dict[str, str]]:
    return {"phones": {}, "linkedin": {}, "om": {}, "ei": {}}


def load_overrides(path: Path) -> dict[str, dict[str, str]]:
    overrides = empty_overrides()
    if not path.exists():
        return overrides
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return overrides
    for key in overrides:
        value = raw.get(key) or {}
        if isinstance(value, dict):
            overrides[key] = {str(item_key): str(item_value) for item_key, item_value in value.items()}
    return overrides


def _enrichment(default: str, override: str | None) -> str:
    if override in {"Yes", "No", "Not listed"}:
        return override
    return default


def county_display(hint: str | None, roes: list[dict[str, object]]) -> str:
    if not hint:
        return ""
    if hint == "cook":
        return "Cook"
    for roe in roes:
        counties = roe.get("counties")
        if not isinstance(counties, list):
            continue
        for county in counties:
            if county_key(str(county)) == hint:
                return str(county)
    return hint


def iter_years(person: dict[str, object]) -> list[dict[str, object]]:
    years = person.get("years")
    if isinstance(years, dict):
        records = []
        for year in SCHOOL_YEARS:
            data = years.get(year)
            if isinstance(data, dict):
                records.append(data)
        return records
    return [
        {
            "employers": person.get("employers") or [],
            "schools": person.get("schools") or [],
        }
    ]


def _empty_year() -> dict[str, object]:
    return {
        "belongs": False,
        "tvi": False,
        "employers": [],
        "schools": [],
        "seen_employers": set(),
        "seen_schools": set(),
        "unplaced_reason": "",
    }


def _ensure_person(
    grouped: dict[tuple[str, str], dict[str, object]],
    first: str,
    last: str,
) -> dict[str, object]:
    key = name_key(first, last)
    person = grouped.get(key)
    if person is None:
        person = {
            "raw_name": (first, last),
            "roles": set(),
            "years": {year: _empty_year() for year in SCHOOL_YEARS},
        }
        grouped[key] = person
        return person
    person["raw_name"] = _prefer_raw_name(person["raw_name"], (first, last))  # type: ignore[arg-type]
    return person


def _add_employer(
    year_data: dict[str, object],
    name: str,
    county: str,
    roe: str | None,
) -> None:
    employer_name = clean_label(name)
    employer_county = clean_label(county)
    if not has_value(employer_name):
        return
    office_id = employer_office_id(employer_name, employer_county)
    seen: set[str] = year_data["seen_employers"]  # type: ignore[assignment]
    if office_id in seen:
        return
    seen.add(office_id)
    employers: list[dict[str, object]] = year_data["employers"]  # type: ignore[assignment]
    employers.append(
        {
            "office_id": office_id,
            "name": employer_name,
            "county": employer_county,
            "roe": roe,
            "is_cps": is_cps(employer_name),
            "is_dhs": is_dhs(employer_name),
        }
    )


def _add_school(
    year_data: dict[str, object],
    site: str,
    district: str,
    region: str,
    fallback_employer: str,
    employer_names: list[str],
    employer_counties: list[str],
    roes: list[dict[str, object]],
) -> None:
    site_name = clean_label(site)
    if not has_value(site_name):
        return
    district_name = clean_label(district)
    label_employer = district_name or fallback_employer
    office_id = school_office_id(label_employer or site_name, site_name)
    seen: set[str] = year_data["seen_schools"]  # type: ignore[assignment]
    if office_id in seen:
        return
    seen.add(office_id)
    schools: list[dict[str, object]] = year_data["schools"]  # type: ignore[assignment]
    schools.append(
        {
            "office_id": office_id,
            "site": site_name,
            "district": district_name,
            "label_employer": label_employer,
            "county_hint": region_county_hint(region, roes),
            "roe": label_for_code(region_code(region, roes), roes),
            "employer_names": employer_names,
            "employer_counties": employer_counties,
        }
    )


def _mark_unplaced(year_data: dict[str, object], reason: str) -> None:
    year_data["belongs"] = True
    if not year_data["unplaced_reason"]:
        year_data["unplaced_reason"] = reason


def _add_credential_office(
    person: dict[str, object],
    year: str,
    name: str,
    county: str,
    roes: list[dict[str, object]],
    regions: list[str],
    reason: str = "",
) -> None:
    year_data = person["years"][year]  # type: ignore[index]
    year_data["belongs"] = True
    if reason:
        _mark_unplaced(year_data, reason)
        return
    if not has_value(name):
        _mark_unplaced(year_data, "No public employer on either log")
        return
    _add_employer(
        year_data,
        name,
        county,
        employer_roe_label(county, name, regions, roes),
    )


def plan_people(
    current_rows: list[dict[str, str]],
    prior_rows: list[dict[str, str]],
    coms_rows: list[dict[str, str]],
    roes: list[dict[str, object]],
    overrides: dict[str, dict[str, str]],
    catis_rows: list[dict[str, str]] | None = None,
    clvt_rows: list[dict[str, str]] | None = None,
    cvrt_rows: list[dict[str, str]] | None = None,
) -> list[dict[str, object]]:
    prior_by_name: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in prior_rows:
        prior_by_name.setdefault(name_key(row["first"], row["last"]), []).append(row)

    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for row in current_rows:
        person = _ensure_person(grouped, row["first"], row["last"])
        roles: set[str] = person["roles"]  # type: ignore[assignment]
        roles.add("TVI")
        year_data = person["years"][YEAR_CURRENT]  # type: ignore[index]
        year_data["belongs"] = True
        year_data["tvi"] = True
        prior = prior_by_name.get(name_key(row["first"], row["last"]), [])
        prior_regions = [item["region"] for item in prior if item.get("region")]
        _add_employer(
            year_data,
            row["employer"],
            row["county"],
            employer_roe_label(row["county"], row["employer"], prior_regions, roes),
        )

    for row in prior_rows:
        person = _ensure_person(grouped, row["first"], row["last"])
        roles = person["roles"]  # type: ignore[assignment]
        roles.add("TVI")
        year_data = person["years"][YEAR_PRIOR]  # type: ignore[index]
        year_data["belongs"] = True
        year_data["tvi"] = True
        district = row.get("district", "")
        site = row.get("site", "")
        region = row.get("region", "")
        if has_value(district):
            county = county_display(region_county_hint(region, roes), roes)
            _add_employer(
                year_data,
                district,
                county,
                label_for_code(region_code(region, roes), roes),
            )
        elif not has_value(site):
            _mark_unplaced(year_data, "No district or school on the 2023–2024 log")
        if has_value(site):
            employers: list[dict[str, object]] = year_data["employers"]  # type: ignore[assignment]
            fallback = str(employers[0]["name"]) if len(employers) == 1 else ""
            _add_school(
                year_data,
                site,
                district,
                region,
                fallback,
                [str(item["name"]) for item in employers],
                [str(item["county"]) for item in employers],
                roes,
            )

    for key, person in grouped.items():
        current_year = person["years"][YEAR_CURRENT]  # type: ignore[index]
        if not current_year["belongs"]:
            continue
        employers = current_year["employers"]  # type: ignore[assignment]
        non_dhs = [item for item in employers if not item["is_dhs"]]
        fallback_employer = str(non_dhs[0]["name"]) if len(non_dhs) == 1 else ""
        for row in prior_by_name.get(key, []):
            _add_school(
                current_year,
                row.get("site", ""),
                row.get("district", ""),
                row.get("region", ""),
                fallback_employer,
                [str(item["name"]) for item in employers],
                [str(item["county"]) for item in employers],
                roes,
            )

    for row in coms_rows:
        person = _ensure_person(grouped, row["first"], row["last"])
        roles = person["roles"]  # type: ignore[assignment]
        roles.add("COMS")

    for row in catis_rows or []:
        person = _ensure_person(grouped, row["first"], row["last"])
        roles = person["roles"]  # type: ignore[assignment]
        roles.add("CATIS")
        prior = prior_by_name.get(name_key(row["first"], row["last"]), [])
        prior_regions = [item["region"] for item in prior if item.get("region")]
        current_year = person["years"][YEAR_CURRENT]  # type: ignore[index]
        prior_year = person["years"][YEAR_PRIOR]  # type: ignore[index]
        if has_value(row.get("employer", "")) and not current_year["employers"]:
            _add_credential_office(
                person,
                YEAR_CURRENT,
                row["employer"],
                row.get("county", ""),
                roes,
                prior_regions,
            )
        if has_value(row.get("district", "")) and not prior_year["employers"] and not prior_year["schools"]:
            county = county_display(
                region_county_hint(prior[0]["region"], roes) if prior else None,
                roes,
            )
            _add_credential_office(
                person,
                YEAR_PRIOR,
                row["district"],
                county,
                roes,
                prior_regions,
            )
            if has_value(row.get("site", "")):
                employers = prior_year["employers"]  # type: ignore[assignment]
                _add_school(
                    prior_year,
                    row.get("site", ""),
                    row["district"],
                    prior[0]["region"] if prior else "",
                    str(employers[0]["name"]) if employers else "",
                    [str(item["name"]) for item in employers],
                    [str(item["county"]) for item in employers],
                    roes,
                )
        if not current_year["belongs"] and not prior_year["belongs"]:
            _mark_unplaced(current_year, "No public employer on either log")
            _mark_unplaced(prior_year, "No public employer on either log")

    for row in clvt_rows or []:
        person = _ensure_person(grouped, row["first"], row["last"])
        roles = person["roles"]  # type: ignore[assignment]
        roles.add("CLVT")
        reason = ""
        if row.get("confirmed") in {True, "True", "true"}:
            reason = ""
        elif has_value(row.get("employer", "")):
            reason = "Employer needs a hand check"
        else:
            reason = "No public employer on either log"
        current_year = person["years"][YEAR_CURRENT]  # type: ignore[index]
        prior_year = person["years"][YEAR_PRIOR]  # type: ignore[index]
        if reason:
            if not current_year["belongs"] and not current_year["employers"]:
                current_year["belongs"] = True
                _mark_unplaced(current_year, reason)
            if not prior_year["belongs"] and not prior_year["employers"]:
                prior_year["belongs"] = True
                _mark_unplaced(prior_year, reason)
            continue
        for year in SCHOOL_YEARS:
            year_data = person["years"][year]  # type: ignore[index]
            if year_data["employers"] or year_data["schools"]:
                continue
            _add_credential_office(
                person, year, row.get("employer", ""), row.get("county", ""), roes, []
            )

    for row in cvrt_rows or []:
        person = _ensure_person(grouped, row["first"], row["last"])
        roles = person["roles"]  # type: ignore[assignment]
        roles.add("CVRT")
        employer = row.get("employer", "")
        reason = ""
        if not has_value(employer):
            reason = "No public employer on either log"
        elif is_dhs(employer):
            reason = "Department of Human Services is not used as a map point"
        for year in SCHOOL_YEARS:
            year_data = person["years"][year]  # type: ignore[index]
            if year_data["employers"] or year_data["schools"]:
                continue
            if reason:
                year_data["belongs"] = True
                _mark_unplaced(year_data, reason)
                continue
            _add_credential_office(person, year, employer, row.get("county", ""), roes, [])

    for row in coms_rows:
        person = grouped[name_key(row["first"], row["last"])]
        current_year = person["years"][YEAR_CURRENT]  # type: ignore[index]
        prior_year = person["years"][YEAR_PRIOR]  # type: ignore[index]
        if current_year["belongs"] or prior_year["belongs"]:
            continue
        current_year["belongs"] = True
        prior_year["belongs"] = True
        _mark_unplaced(current_year, "No public employer on either log")
        _mark_unplaced(prior_year, "No public employer on either log")

    people: list[dict[str, object]] = []
    for person in grouped.values():
        raw_first, raw_last = person["raw_name"]  # type: ignore[misc]
        person_id = slug(display_name(raw_first, raw_last))
        years = {}
        any_dhs = False
        for year in SCHOOL_YEARS:
            year_data = person["years"][year]  # type: ignore[index]
            employers = year_data["employers"]  # type: ignore[assignment]
            if any(item["is_dhs"] for item in employers):
                any_dhs = True
            years[year] = {
                "belongs": year_data["belongs"],
                "tvi": year_data["tvi"],
                "employers": employers,
                "schools": year_data["schools"],
                "unplaced_reason": year_data["unplaced_reason"],
            }
        roles = ordered_roles(person["roles"])  # type: ignore[arg-type]
        default_om = "Yes" if "COMS" in roles else "Not listed"
        default_ei = "Yes" if any_dhs else "Not listed"
        people.append(
            {
                "id": person_id,
                "name": display_name(raw_first, raw_last),
                "roles": roles,
                "om": _enrichment(default_om, overrides.get("om", {}).get(person_id)),
                "ei": _enrichment(default_ei, overrides.get("ei", {}).get(person_id)),
                "linkedin": overrides.get("linkedin", {}).get(person_id) or "Not listed",
                "years": years,
            }
        )
    people.sort(key=lambda item: str(item["name"]))
    return people


def _numbers_compatible(left: frozenset[str], right: frozenset[str]) -> bool:
    if not left or not right:
        return True
    return left == right


def match_employer(
    name: str, county: str, leas: list[dict[str, object]]
) -> dict[str, object] | None:
    """Match one employer to a public NCES district or cooperative office."""
    if is_dhs(name):
        return None
    expanded = expand_name(name)
    query_numbers = district_numbers(expanded)
    query_content = content_tokens(expanded)
    query_words = distinctive_words(expanded)
    county_name = county_key(county)
    exact = [
        lea
        for lea in leas
        if lea.get("expanded") == expanded and in_illinois(lea.get("lat"), lea.get("lng"))  # type: ignore[arg-type]
    ]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        in_county = [lea for lea in exact if lea.get("county") == county_name]
        if len(in_county) == 1:
            return in_county[0]
        return None

    def _score_lea(lea: dict[str, object]) -> float | None:
        if not in_illinois(lea.get("lat"), lea.get("lng")):  # type: ignore[arg-type]
            return None
        lea_expanded = str(lea.get("expanded") or "")
        lea_numbers = lea.get("numbers")
        if not isinstance(lea_numbers, frozenset):
            lea_numbers = district_numbers(lea_expanded)
        if not _numbers_compatible(query_numbers, lea_numbers):
            return None
        lea_content = content_tokens(lea_expanded)
        lea_words = distinctive_words(lea_expanded)
        score = jaccard(query_content, lea_content)
        shared_words = query_words & lea_words
        same_number = bool(query_numbers) and query_numbers == lea_numbers
        if shared_words and same_number and score >= 0.5:
            return score
        if shared_words and score >= 0.66:
            return score
        return None

    if not county_name:
        statewide: list[tuple[float, dict[str, object]]] = []
        for lea in leas:
            score = _score_lea(lea)
            if score is None:
                continue
            statewide.append((score, lea))
        if not statewide:
            return None
        statewide.sort(key=lambda item: (-item[0], str(item[1].get("name"))))
        if len(statewide) > 1 and statewide[1][0] >= statewide[0][0] - 0.08:
            return None
        return statewide[0][1]

    scored: list[tuple[float, dict[str, object]]] = []
    for lea in leas:
        if lea.get("county") != county_name:
            continue
        score = _score_lea(lea)
        if score is None:
            continue
        scored.append((score, lea))
    if not scored and query_numbers and query_words:
        # "CUSD 308" in Oswego carries the place name on the city, not the title.
        city_hits: list[dict[str, object]] = []
        for lea in leas:
            if lea.get("county") != county_name:
                continue
            if not in_illinois(lea.get("lat"), lea.get("lng")):  # type: ignore[arg-type]
                continue
            lea_expanded = str(lea.get("expanded") or "")
            lea_numbers = lea.get("numbers")
            if not isinstance(lea_numbers, frozenset):
                lea_numbers = district_numbers(lea_expanded)
            if lea_numbers != query_numbers:
                continue
            city_words = {word for word in str(lea.get("city") or "").split(" ") if word}
            if query_words & (distinctive_words(lea_expanded) | city_words):
                city_hits.append(lea)
        if len(city_hits) == 1:
            return city_hits[0]
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], str(item[1].get("name"))))
    best_score, best = scored[0]
    if len(scored) > 1 and scored[1][0] >= best_score - 0.08:
        return None
    return best


def match_school(site: str, schools: list[dict[str, object]]) -> dict[str, object] | None:
    expanded_site = expand_name(site)
    site_words = distinctive_words(expanded_site)
    scored: list[tuple[float, dict[str, object]]] = []
    for school in schools:
        if not in_illinois(school.get("lat"), school.get("lng")):  # type: ignore[arg-type]
            continue
        expanded = str(school.get("expanded") or "")
        if expanded == expanded_site:
            score = 1.0
        else:
            score = jaccard(content_tokens(expanded_site), content_tokens(expanded))
            school_words = distinctive_words(expanded)
            if site_words and site_words <= school_words:
                score = max(score, 0.9 if len(site_words) >= 2 else 0.0)
        if score >= 0.8:
            scored.append((score, school))
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], str(item[1].get("name"))))
    if len(scored) > 1 and scored[1][0] >= scored[0][0] - 0.05:
        return None
    return scored[0][1]


def lea_kind(name: str) -> str:
    expanded = expand_name(name)
    if "cooperative" in expanded or "joint agreement" in expanded:
        return "cooperative_office"
    if "special education" in expanded and "school district" not in expanded:
        return "cooperative_office"
    if "association" in expanded and "school district" not in expanded:
        return "cooperative_office"
    return "district_office"


def _office_shell(
    office_id: str,
    name: str,
    county: str,
    kind: str,
    lat: float,
    lng: float,
    address: str,
    source_url: str,
    matched_name: str,
    phone: str,
) -> dict[str, object]:
    return {
        "id": office_id,
        "name": name,
        "county": county,
        "kind": kind,
        "lat": lat,
        "lng": lng,
        "address": address,
        "source_url": source_url,
        "matched_name": matched_name,
        "phone": phone or "Not listed",
    }


def label_from_office_county(
    county: str, fallback: str | None, roes: list[dict[str, object]] | None
) -> str | None:
    """Use the county of the public office when that county belongs to one ROE."""
    if not roes:
        return fallback
    key = county_key(county)
    if not key or key == "cook":
        return fallback
    _by_code, by_county, _by_set = _roe_indexes(roes)
    matches = by_county.get(key, set())
    if len(matches) == 1:
        return label_for_code(next(iter(matches)), roes)
    return fallback


def year_omitted_note(year: str, omitted: int, dhs_people: int, other_people: int) -> str:
    label = year.replace("-", "–")
    if omitted == 1:
        note = f"1 person on the {label} log is not in this search."
    else:
        note = f"{omitted} people on the {label} log are not in this search."
    if dhs_people == 1:
        note += (
            " 1 works for the Department of Human Services and is left off the map "
            "unless a school building is known."
        )
    elif dhs_people > 1:
        note += (
            f" {dhs_people} work for the Department of Human Services and are left off the map "
            "unless a school building is known."
        )
    if other_people == 1:
        note += " 1 has an employer that could not be matched to a public office."
    elif other_people > 1:
        note += (
            f" {other_people} have an employer that could not be matched to a public office."
        )
    return note


def _place_year(
    year_data: dict[str, object],
    cache: dict[str, dict[str, object]],
    overrides: dict[str, dict[str, str]],
    roes: list[dict[str, object]] | None,
    offices: dict[str, dict[str, object]],
) -> tuple[list[dict[str, object]], str]:
    """Return locations for one school year and a reason when none can be used."""
    employers: list[dict[str, object]] = year_data.get("employers") or []  # type: ignore[assignment]
    schools: list[dict[str, object]] = year_data.get("schools") or []  # type: ignore[assignment]
    employer_points: list[dict[str, object]] = []
    dhs_only = False
    unmatched = False
    for employer in employers:
        office_id = str(employer["office_id"])
        if employer["is_dhs"]:
            dhs_only = True
            continue
        cached = cache.get(office_id)
        if not cached or not in_illinois(cached.get("lat"), cached.get("lng")):  # type: ignore[arg-type]
            unmatched = True
            continue
        phone = overrides.get("phones", {}).get(office_id) or "Not listed"
        office = _office_shell(
            office_id,
            str(employer["name"]),
            str(employer["county"]),
            str(cached.get("kind") or "district_office"),
            float(cached["lat"]),
            float(cached["lng"]),
            str(cached.get("address") or ""),
            str(cached.get("source_url") or ""),
            str(cached.get("matched_name") or ""),
            phone,
        )
        offices[office_id] = office
        detail = "district office" if employer["is_cps"] else None
        employer_roe = label_from_office_county(
            str(cached.get("county") or employer["county"]),
            employer.get("roe") if isinstance(employer.get("roe"), str) else None,
            roes,
        )
        employer_points.append(
            {
                "office_id": office_id,
                "phone_office_id": office_id,
                "label": location_label(str(employer["name"]), detail, employer_roe),
                "roe": employer_roe or "",
                "is_cps": employer["is_cps"],
                "lat": office["lat"],
                "lng": office["lng"],
            }
        )
    school_points: list[dict[str, object]] = []
    for school in schools:
        office_id = str(school["office_id"])
        cached = cache.get(office_id)
        if not cached or not in_illinois(cached.get("lat"), cached.get("lng")):  # type: ignore[arg-type]
            continue
        label_employer = str(school.get("label_employer") or "")
        phone_office_id = ""
        for employer in employers:
            office_id_employer = str(employer["office_id"])
            if employer["name"] == label_employer and not employer["is_dhs"] and office_id_employer in offices:
                phone_office_id = office_id_employer
                break
        if not phone_office_id:
            for employer in employers:
                office_id_employer = str(employer["office_id"])
                if not employer["is_dhs"] and office_id_employer in offices:
                    phone_office_id = office_id_employer
                    break
        school_name = str(cached.get("matched_name") or school["site"])
        school_roe = label_from_office_county(
            str(cached.get("county") or ""),
            school.get("roe") if isinstance(school.get("roe"), str) else None,
            roes,
        )
        office = _office_shell(
            office_id,
            school_name,
            str(cached.get("county") or ""),
            "school",
            float(cached["lat"]),
            float(cached["lng"]),
            str(cached.get("address") or ""),
            str(cached.get("source_url") or NCES_SOURCE),
            school_name,
            "Not listed",
        )
        offices[office_id] = office
        school_points.append(
            {
                "office_id": office_id,
                "phone_office_id": phone_office_id,
                "label": location_label(label_employer, school_name, school_roe),
                "roe": school_roe or "",
                "lat": office["lat"],
                "lng": office["lng"],
            }
        )
    if school_points:
        employer_points = [point for point in employer_points if not point["is_cps"]]
        kept_employers = []
        for point in employer_points:
            near_school = False
            for school_point in school_points:
                distance = haversine_miles(
                    float(point["lat"]),
                    float(point["lng"]),
                    float(school_point["lat"]),
                    float(school_point["lng"]),
                )
                if distance <= SAME_BUILDING_MILES:
                    near_school = True
                    break
            if not near_school:
                kept_employers.append(point)
        employer_points = kept_employers
    locations: list[dict[str, object]] = []
    for point in employer_points + school_points:
        locations.append(
            {
                "office_id": point["office_id"],
                "phone_office_id": point["phone_office_id"],
                "label": point["label"],
                "roe": point.get("roe") or "",
            }
        )
    locations.sort(key=lambda item: str(item["label"]))
    if locations:
        return locations, ""
    planned_reason = str(year_data.get("unplaced_reason") or "")
    if planned_reason:
        return [], planned_reason
    if dhs_only and not unmatched:
        return [], "Department of Human Services is not used as a map point"
    if unmatched or employers or schools:
        return [], "No confident public office match"
    if year_data.get("belongs"):
        return [], "No public employer on either log"
    return [], ""


def compile_directory(
    people: list[dict[str, object]],
    cache: dict[str, dict[str, object]],
    overrides: dict[str, dict[str, str]],
    roes: list[dict[str, object]] | None = None,
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, dict[str, object]],
]:
    """Attach cached coordinates and drop offices the search must not use."""
    placed_people: list[dict[str, object]] = []
    offices: dict[str, dict[str, object]] = {}
    unplaced_people: list[dict[str, object]] = []
    omitted_counts = {year: 0 for year in SCHOOL_YEARS}
    dhs_counts = {year: 0 for year in SCHOOL_YEARS}
    other_counts = {year: 0 for year in SCHOOL_YEARS}

    for person in people:
        year_locations: dict[str, list[dict[str, object]]] = {}
        roles = person.get("roles") or ["TVI"]
        if not isinstance(roles, list):
            roles = ["TVI"]
        planned_years = person.get("years")
        if not isinstance(planned_years, dict):
            planned_years = {
                YEAR_CURRENT: {
                    "belongs": True,
                    "tvi": True,
                    "employers": person.get("employers") or [],
                    "schools": person.get("schools") or [],
                    "unplaced_reason": "",
                }
            }
        for year in SCHOOL_YEARS:
            year_data = planned_years.get(year)
            if not isinstance(year_data, dict):
                year_data = {
                    "belongs": False,
                    "tvi": False,
                    "employers": [],
                    "schools": [],
                    "unplaced_reason": "",
                }
            locations, reason = _place_year(year_data, cache, overrides, roes, offices)
            year_locations[year] = locations
            belongs = bool(year_data.get("belongs"))
            tvi_log = bool(year_data.get("tvi"))
            if belongs and not locations:
                unplaced_people.append(
                    {
                        "id": person["id"],
                        "name": person["name"],
                        "roles": roles,
                        "year": year,
                        "tvi": tvi_log,
                        "reason": reason or "No confident public office match",
                    }
                )
                if tvi_log:
                    omitted_counts[year] += 1
                    if str(reason).startswith("Department of Human Services"):
                        dhs_counts[year] += 1
                    elif reason == "No confident public office match":
                        other_counts[year] += 1
        if not any(year_locations[year] for year in SCHOOL_YEARS):
            continue
        placed_people.append(
            {
                "id": person["id"],
                "name": person["name"],
                "roles": roles,
                "om": person["om"],
                "ei": person["ei"],
                "linkedin": person["linkedin"],
                "years": year_locations,
            }
        )

    stats = {
        year: {
            "omitted_people": omitted_counts[year],
            "omitted_note": year_omitted_note(
                year, omitted_counts[year], dhs_counts[year], other_counts[year]
            ),
        }
        for year in SCHOOL_YEARS
    }
    office_list = sorted(offices.values(), key=lambda item: str(item["id"]))
    unplaced_people.sort(key=lambda item: (str(item["year"]), str(item["name"])))
    return placed_people, office_list, unplaced_people, stats
