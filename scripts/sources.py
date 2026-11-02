"""Read the teacher logs and the credential lookup sheets."""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from scripts.tvi_data import clean_label, clean_source_label


def _rows(path: Path, sheet_name: str) -> list[dict[str, str]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        worksheet = workbook[sheet_name]
        iterator = worksheet.iter_rows(values_only=True)
        header = [str(cell).strip() if cell is not None else "" for cell in next(iterator)]
        records: list[dict[str, str]] = []
        for row in iterator:
            if not any(cell not in (None, "") for cell in row):
                continue
            values = {
                header[index]: "" if row[index] is None else str(row[index])
                for index in range(min(len(header), len(row)))
            }
            records.append(values)
        return records
    finally:
        workbook.close()


def _cell(row: dict[str, str], *names: str) -> str:
    for name in names:
        if name in row:
            return clean_label(row[name])
    return ""


def load_current(path: Path) -> list[dict[str, str]]:
    people = []
    for row in _rows(path, "results"):
        first = _cell(row, "First Name")
        last = _cell(row, "Last Name")
        employer = _cell(row, "Entity Name")
        county = _cell(row, "County")
        if not first or not last or not employer:
            continue
        people.append(
            {"first": first, "last": last, "employer": employer, "county": county}
        )
    return people


def load_prior(path: Path) -> list[dict[str, str]]:
    people = []
    for row in _rows(path, "Combined"):
        first = _cell(row, "FirstName", "First Name")
        last = _cell(row, "LastName", "Last Name")
        if not first or not last:
            continue
        people.append(
            {
                "first": first,
                "last": last,
                "region": _cell(row, "Region"),
                "district": clean_source_label(_cell(row, "District")),
                "site": _cell(row, "Site"),
            }
        )
    return people


def load_coms(path: Path) -> list[dict[str, str]]:
    people = []
    for row in _rows(path, "COMS lookup"):
        first = _cell(row, "First Name")
        last = _cell(row, "Last Name")
        if not first or not last:
            continue
        people.append({"first": first, "last": last})
    return people


def load_catis(path: Path) -> list[dict[str, str]]:
    people = []
    for row in _rows(path, "CATIS lookup"):
        first = _cell(row, "First Name")
        last = _cell(row, "Last Name")
        if not first or not last:
            continue
        people.append(
            {
                "first": first,
                "last": last,
                "employer": _cell(row, "2024-2025 employer"),
                "county": _cell(row, "2024-2025 county"),
                "district": clean_source_label(_cell(row, "2023-2024 district")),
                "site": _cell(row, "2023-2024 site"),
            }
        )
    return people


def load_clvt(path: Path) -> list[dict[str, str]]:
    people = []
    for row in _rows(path, "CLVT lookup"):
        first = _cell(row, "First name", "First Name")
        last = _cell(row, "Last name", "Last Name")
        if not first or not last:
            continue
        finding = _cell(row, "School or district finding")
        people.append(
            {
                "first": first,
                "last": last,
                "employer": _cell(row, "Employer"),
                "county": "",
                "confirmed": finding.casefold() == "confirmed",
                "finding": finding,
            }
        )
    return people


def load_cvrt(path: Path) -> list[dict[str, str]]:
    people = []
    for row in _rows(path, "IL CVRTs"):
        first = _cell(row, "First Name")
        last = _cell(row, "Last Name")
        if not first or not last:
            continue
        people.append(
            {
                "first": first,
                "last": last,
                "employer": _cell(row, "Employer"),
                "county": "",
                "employer_type": _cell(row, "Employer Type"),
            }
        )
    return people
