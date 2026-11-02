#!/usr/bin/env python3
"""Look up blank employers in the 2024–2025 teacher log.

A location is accepted only when a public Illinois salary record names a
school, district, or special-education cooperative and the record year is
2023, 2024, 2025, or 2026. Salary amounts are never stored.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "raw_foia" / "Teacher_Logs_2024-2025.xlsx"
CACHE = Path("/tmp/tvi-govsalaries")
RESULT = Path("/tmp/tvi_null_lookup.json")
YEARS = {"2023", "2024", "2025", "2026"}
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

SCHOOL_RE = re.compile(
    r"school district|community unit|community consolidated|"
    r"high school|grade school|elementary school|public schools|"
    r"special education|spec educ|education services|educational service|"
    r"educational coop|education coop|center for rehabilitation and education|"
    r"school for the|laboratory school|board of education|"
    r"joint agreement|special services|exceptional learners|learners collaborative|"
    r"\b(cusd|ccsd|chsd|hsd|esd|psd|gsd)\b|\bsd\s*\d",
    re.IGNORECASE,
)
PAGE_RE = re.compile(r'href="(/search\?[^"]*page=\d+[^"]*)"', re.IGNORECASE)
NON_SCHOOL_RE = re.compile(
    r"university|college|park district|conservation|water reclamation|"
    r"\blibrary\b|fire protection|\bpolice\b|\bsheriff\b|"
    r"department of human services|human services|"
    r"housing authority|sanitary|hospital|judicial",
    re.IGNORECASE,
)
ROW_RE = re.compile(
    r'<td><a href="(/[^"]+)">([^<]+)</a></td><td>([A-Z]{2})</td><td>(\d{4})</td>'
    r"\s*<td>(.*?)</td>\s*<td><a href=\"(/salaries/[^\"]+)\">([^<]+)</a></td>",
    re.DOTALL,
)
COUNT_RE = re.compile(r"has (\d+) Salary", re.IGNORECASE)
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def blank_entity(value: object) -> bool:
    text = "" if value is None else str(value).strip()
    return text == "" or text.upper() == "NULL"


def is_school(employer: str) -> bool:
    if NON_SCHOOL_RE.search(employer) and not SCHOOL_RE.search(employer):
        return False
    if re.search(r"university|\bcollege\b", employer, re.IGNORECASE) and not re.search(
        r"school district|high school|laboratory school", employer, re.IGNORECASE
    ):
        return False
    if re.search(r"\bcooperative\b", employer, re.IGNORECASE) and not re.search(
        r"electric|water|telephone|farm|credit", employer, re.IGNORECASE
    ):
        return True
    if re.search(
        r"park district|conservation|water reclamation|human services",
        employer,
        re.IGNORECASE,
    ):
        return False
    return SCHOOL_RE.search(employer) is not None


def clean_token(token: str) -> str:
    return token.strip(".,").casefold()


def name_matches(record_name: str, first: str, last: str) -> bool:
    tokens = [clean_token(part) for part in record_name.split() if clean_token(part)]
    while tokens and tokens[-1] in SUFFIXES:
        tokens.pop()
    if len(tokens) < 2:
        return False
    first_key = clean_token(first)
    last_key = clean_token(last)
    last_tokens = last_key.split()
    if tokens[-len(last_tokens) :] != last_tokens:
        if (
            len(tokens) >= len(last_tokens) + 1
            and tokens[-len(last_tokens) - 1 : -1] == last_tokens
            and len(tokens[-1]) == 1
        ):
            given = tokens[: -len(last_tokens) - 1]
        else:
            return False
    else:
        given = tokens[: -len(last_tokens)]
    if not given:
        return False
    first_parts = first_key.split()
    if given[: len(first_parts)] != first_parts:
        return False
    return True


def fetch(url: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    key = urllib.parse.quote(url, safe="")
    path = CACHE / key
    if path.exists() and path.stat().st_size > 0:
        return path.read_text(errors="replace")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            html = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        if error.code == 404:
            html = ""
        else:
            raise
    path.write_text(html)
    time.sleep(0.35)
    return html


def parse_records(html: str) -> tuple[list[dict[str, str]], int | None]:
    count_match = COUNT_RE.search(html)
    declared = int(count_match.group(1)) if count_match else None
    records = []
    for match in ROW_RE.finditer(html):
        profile, name, state, year, _title, employer_path, employer = match.groups()
        records.append(
            {
                "name": name.strip(),
                "state": state,
                "year": year,
                "employer": employer.replace("&amp;", "&").strip(),
                "profile": "https://govsalaries.com" + profile,
            }
        )
    return records, declared


def search_pages(url: str) -> str:
    return fetch(url)


def search_person(first: str, last: str) -> tuple[list[dict[str, str]], str]:
    query = urllib.parse.urlencode(
        {"state": "illinois", "employee": f"{first} {last}"}
    )
    url = f"https://govsalaries.com/search?{query}"
    queue = [url]
    seen_pages = set()
    records: list[dict[str, str]] = []
    declared = None
    while queue:
        page = queue.pop(0)
        if page in seen_pages:
            continue
        seen_pages.add(page)
        html = search_pages(page)
        parsed, page_declared = parse_records(html)
        if page_declared is not None:
            declared = page_declared
        records.extend(parsed)
        for href in PAGE_RE.findall(html):
            next_url = "https://govsalaries.com" + href.replace("&amp;", "&")
            if next_url not in seen_pages:
                queue.append(next_url)
    unique = []
    seen_rows = set()
    for row in records:
        key = (row["name"], row["state"], row["year"], row["employer"], row["profile"])
        if key in seen_rows:
            continue
        seen_rows.add(key)
        unique.append(row)
    if declared is not None and len(unique) < declared:
        unique.append(
            {
                "name": "",
                "state": "",
                "year": "",
                "employer": "",
                "profile": "",
                "incomplete": "true",
                "declared": str(declared),
                "parsed": str(len(unique)),
            }
        )
    return unique, url


def person_key(record_name: str) -> str:
    tokens = [clean_token(part) for part in record_name.split() if clean_token(part)]
    while tokens and tokens[-1] in SUFFIXES:
        tokens.pop()
    if len(tokens) >= 3 and len(tokens[-1]) == 1:
        return tokens[-1]
    if len(tokens) >= 3:
        return " ".join(tokens[1:-1])
    return ""


def decide(first: str, last: str, records: list[dict[str, str]], source: str) -> dict[str, object]:
    incomplete = [row for row in records if row.get("incomplete")]
    usable = [row for row in records if not row.get("incomplete")]
    matched = [
        row
        for row in usable
        if row["state"] == "IL"
        and row["year"] in YEARS
        and name_matches(row["name"], first, last)
    ]
    schools: dict[str, list[dict[str, str]]] = defaultdict(list)
    other: dict[str, list[str]] = defaultdict(list)
    for row in matched:
        if is_school(row["employer"]):
            schools[row["employer"]].append(row)
        else:
            other[row["employer"]].append(row["year"])
    identities = {person_key(row["name"]) for rows in schools.values() for row in rows}
    earlier_note = ""
    if len(schools) > 1 and len(identities) == 1:
        year_sets = []
        for rows in schools.values():
            year_sets.append({row["year"] for row in rows})
        overlap = False
        for index, left in enumerate(year_sets):
            for right in year_sets[index + 1 :]:
                if left & right:
                    overlap = True
        if not overlap:
            latest_year = max(year for rows in schools.values() for year in (row["year"] for row in rows))
            chosen = [
                (employer, rows)
                for employer, rows in schools.items()
                if any(row["year"] == latest_year for row in rows)
            ]
            if len(chosen) == 1:
                earlier = []
                for employer, rows in sorted(schools.items()):
                    if employer == chosen[0][0]:
                        continue
                    years = ", ".join(sorted({row["year"] for row in rows}))
                    earlier.append(f"{employer} ({years})")
                schools = {chosen[0][0]: chosen[0][1]}
                if earlier:
                    earlier_note = (
                        " Earlier school employer in this window: " + "; ".join(earlier) + "."
                    )
    if incomplete:
        status = "incomplete"
        note = (
            "Lookup incomplete: the public page listed more salary records "
            "than the parser read. Employer left blank."
        )
        entity = "NULL"
        year = ""
    elif len(schools) == 1:
        employer, rows = next(iter(schools.items()))
        years = sorted({row["year"] for row in rows})
        names = sorted({row["name"] for row in rows})
        status = "match"
        entity = employer
        year = years[-1]
        note = (
            f"Match: {employer} ({', '.join(years)}). "
            f"Public record name: {', '.join(names)}.{earlier_note}"
        )
        profiles = sorted({row["profile"] for row in rows})
        if len(profiles) == 1:
            source = profiles[0]
    elif len(schools) > 1:
        status = "ambiguous"
        entity = "NULL"
        year = ""
        parts = []
        for employer, rows in sorted(schools.items()):
            years = ", ".join(sorted({row["year"] for row in rows}))
            names = ", ".join(sorted({row["name"] for row in rows}))
            parts.append(f"{employer} [{years}; {names}]")
        note = (
            f"Ambiguous: {len(schools)} Illinois school, district, or cooperative "
            f"employers in 2023–2026 — " + "; ".join(parts)
        )
    elif other:
        status = "not_a_school"
        entity = "NULL"
        year = ""
        parts = [
            f"{employer} ({', '.join(sorted(set(years)))})"
            for employer, years in sorted(other.items())
        ]
        note = (
            "Not a school, district, or cooperative: Illinois 2023–2026 records are "
            + "; ".join(parts)
        )
    else:
        status = "no_record"
        entity = "NULL"
        year = ""
        note = "No record: no Illinois school, district, or cooperative salary record for 2023–2026."
    return {
        "first": first,
        "last": last,
        "status": status,
        "entity": entity,
        "year": year,
        "note": note,
        "source": source,
        "incomplete": bool(incomplete),
    }


def main() -> None:
    workbook = load_workbook(WORKBOOK)
    sheet = workbook.active
    decisions = []
    for cells in sheet.iter_rows(min_row=2):
        first = "" if cells[0].value is None else str(cells[0].value).strip()
        last = "" if cells[1].value is None else str(cells[1].value).strip()
        if not first and not last:
            continue
        if not blank_entity(cells[2].value):
            continue
        records, source = search_person(first, last)
        item = decide(first, last, records, source)
        decisions.append(item)
        print(f"{item['status']:12} {first} {last}")
    RESULT.write_text(json.dumps(decisions, indent=2))
    by_name = {
        (str(item["first"]).casefold(), str(item["last"]).casefold()): item
        for item in decisions
    }
    updated = 0
    for cells in sheet.iter_rows(min_row=2):
        first = "" if cells[0].value is None else str(cells[0].value).strip()
        last = "" if cells[1].value is None else str(cells[1].value).strip()
        if not first and not last:
            continue
        if not blank_entity(cells[2].value):
            continue
        item = by_name.get((first.casefold(), last.casefold()))
        if item is None:
            continue
        if item["status"] == "match":
            cells[2].value = item["entity"]
            cells[3].value = item["year"]
        cells[4].value = item["note"]
        cells[5].value = item["source"]
        updated += 1
    workbook.save(WORKBOOK)
    print("UPDATED", updated)
    counts: dict[str, int] = defaultdict(int)
    for item in decisions:
        counts[str(item["status"])] += 1
    print("WROTE", RESULT)
    print(dict(counts))


if __name__ == "__main__":
    main()
