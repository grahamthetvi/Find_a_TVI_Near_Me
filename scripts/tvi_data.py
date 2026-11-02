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


def plan_people(
    current_rows: list[dict[str, str]],
    prior_rows: list[dict[str, str]],
    coms_rows: list[dict[str, str]],
    roes: list[dict[str, object]],
    overrides: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    prior_by_name: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in prior_rows:
        prior_by_name.setdefault(name_key(row["first"], row["last"]), []).append(row)
    coms_names = {name_key(row["first"], row["last"]) for row in coms_rows}

    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for row in current_rows:
        key = name_key(row["first"], row["last"])
        person = grouped.get(key)
        if person is None:
            person = {
                "raw_name": (row["first"], row["last"]),
                "employers": [],
                "seen_employers": set(),
            }
            grouped[key] = person
        person["raw_name"] = _prefer_raw_name(person["raw_name"], (row["first"], row["last"]))  # type: ignore[arg-type]
        office_id = employer_office_id(row["employer"], row["county"])
        seen: set[str] = person["seen_employers"]  # type: ignore[assignment]
        if office_id in seen:
            continue
        seen.add(office_id)
        employers: list[dict[str, object]] = person["employers"]  # type: ignore[assignment]
        employers.append(
            {
                "office_id": office_id,
                "name": clean_label(row["employer"]),
                "county": clean_label(row["county"]),
            }
        )

    people: list[dict[str, object]] = []
    for key, person in grouped.items():
        raw_first, raw_last = person["raw_name"]  # type: ignore[misc]
        person_id = slug(display_name(raw_first, raw_last))
        prior = prior_by_name.get(key, [])
        prior_regions = [row["region"] for row in prior if row.get("region")]
        employers = []
        for employer in person["employers"]:  # type: ignore[union-attr]
            name = str(employer["name"])
            county = str(employer["county"])
            employers.append(
                {
                    **employer,
                    "roe": employer_roe_label(county, name, prior_regions, roes),
                    "is_cps": is_cps(name),
                    "is_dhs": is_dhs(name),
                }
            )
        non_dhs = [item for item in employers if not item["is_dhs"]]
        fallback_employer = non_dhs[0]["name"] if len(non_dhs) == 1 else ""
        schools = []
        seen_schools: set[str] = set()
        for row in prior:
            site = clean_label(row.get("site", ""))
            if not site:
                continue
            district = clean_label(row.get("district", ""))
            label_employer = district or str(fallback_employer)
            office_id = school_office_id(label_employer or site, site)
            if office_id in seen_schools:
                continue
            seen_schools.add(office_id)
            region = row.get("region", "")
            schools.append(
                {
                    "office_id": office_id,
                    "site": site,
                    "district": district,
                    "label_employer": label_employer,
                    "county_hint": region_county_hint(region, roes),
                    "roe": label_for_code(region_code(region, roes), roes),
                    "employer_names": [item["name"] for item in employers],
                    "employer_counties": [item["county"] for item in employers],
                }
            )
        default_om = "Yes" if key in coms_names else "Not listed"
        default_ei = "Yes" if any(item["is_dhs"] for item in employers) else "Not listed"
        people.append(
            {
                "id": person_id,
                "name": display_name(raw_first, raw_last),
                "om": _enrichment(default_om, overrides.get("om", {}).get(person_id)),
                "ei": _enrichment(default_ei, overrides.get("ei", {}).get(person_id)),
                "linkedin": overrides.get("linkedin", {}).get(person_id) or "Not listed",
                "employers": employers,
                "schools": schools,
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

    scored: list[tuple[float, dict[str, object]]] = []
    for lea in leas:
        if lea.get("county") != county_name:
            continue
        if not in_illinois(lea.get("lat"), lea.get("lng")):  # type: ignore[arg-type]
            continue
        lea_expanded = str(lea.get("expanded") or "")
        lea_numbers = lea.get("numbers")
        if not isinstance(lea_numbers, frozenset):
            lea_numbers = district_numbers(lea_expanded)
        if not _numbers_compatible(query_numbers, lea_numbers):
            continue
        lea_content = content_tokens(lea_expanded)
        lea_words = distinctive_words(lea_expanded)
        score = jaccard(query_content, lea_content)
        shared_words = query_words & lea_words
        same_number = bool(query_numbers) and query_numbers == lea_numbers
        if shared_words and same_number and score >= 0.5:
            scored.append((score, lea))
        elif shared_words and score >= 0.66:
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


def compile_directory(
    people: list[dict[str, object]],
    cache: dict[str, dict[str, object]],
    overrides: dict[str, dict[str, str]],
    roes: list[dict[str, object]] | None = None,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], int]:
    """Attach cached coordinates and drop offices the search must not use."""
    placed_people: list[dict[str, object]] = []
    offices: dict[str, dict[str, object]] = {}
    unplaced: dict[str, dict[str, object]] = {}
    omitted = 0

    for person in people:
        locations: list[dict[str, object]] = []
        employer_points: list[dict[str, object]] = []
        for employer in person["employers"]:  # type: ignore[union-attr]
            office_id = str(employer["office_id"])
            if employer["is_dhs"]:
                unplaced[office_id] = {
                    "name": employer["name"],
                    "county": employer["county"],
                    "people": unplaced.get(office_id, {}).get("people", 0) + 1,
                    "reason": "Department of Human Services is not used as a map point",
                }
                continue
            cached = cache.get(office_id)
            if not cached or not in_illinois(cached.get("lat"), cached.get("lng")):  # type: ignore[arg-type]
                current = unplaced.get(office_id, {})
                unplaced[office_id] = {
                    "name": employer["name"],
                    "county": employer["county"],
                    "people": current.get("people", 0) + 1,
                    "reason": "No confident public office match",
                }
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
                    "is_cps": employer["is_cps"],
                    "lat": office["lat"],
                    "lng": office["lng"],
                }
            )
        school_points: list[dict[str, object]] = []
        for school in person["schools"]:  # type: ignore[union-attr]
            office_id = str(school["office_id"])
            cached = cache.get(office_id)
            if not cached or not in_illinois(cached.get("lat"), cached.get("lng")):  # type: ignore[arg-type]
                continue
            label_employer = str(school.get("label_employer") or "")
            phone_office_id = ""
            for employer in person["employers"]:  # type: ignore[union-attr]
                if employer["name"] == label_employer and not employer["is_dhs"]:
                    phone_office_id = str(employer["office_id"])
                    break
            if not phone_office_id:
                for employer in person["employers"]:  # type: ignore[union-attr]
                    if not employer["is_dhs"]:
                        phone_office_id = str(employer["office_id"])
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
        for point in employer_points + school_points:
            locations.append(
                {
                    "office_id": point["office_id"],
                    "phone_office_id": point["phone_office_id"],
                    "label": point["label"],
                }
            )
        if not locations:
            omitted += 1
            continue
        locations.sort(key=lambda item: str(item["label"]))
        placed_people.append(
            {
                "id": person["id"],
                "name": person["name"],
                "om": person["om"],
                "ei": person["ei"],
                "linkedin": person["linkedin"],
                "locations": locations,
            }
        )

    office_list = sorted(offices.values(), key=lambda item: str(item["id"]))
    unplaced_list = sorted(unplaced.values(), key=lambda item: (-int(item["people"]), str(item["name"])))
    return placed_people, office_list, unplaced_list, omitted
