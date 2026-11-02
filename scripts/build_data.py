"""Write the ROE list, office file, and teacher file the page searches."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.sources import load_coms, load_current, load_prior
from scripts.tvi_data import compile_directory, load_overrides, load_roes, plan_people, write_json


def load_cache(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    offices = payload.get("offices") if isinstance(payload, dict) else None
    if not isinstance(offices, dict):
        return {}
    return {str(key): value for key, value in offices.items() if isinstance(value, dict)}


def main() -> None:
    data = ROOT / "data"
    raw = ROOT / "raw_foia"
    roes = load_roes(raw / "illinois_roe_and_county_directory.md")
    overrides = load_overrides(data / "overrides.json")
    people = plan_people(
        load_current(raw / "Teacher_Logs_2024-2025.xlsx"),
        load_prior(raw / "Teacher_Logs_2023-2024.xlsx"),
        load_coms(raw / "Illinois_COMS_govsalaries.xlsx"),
        roes,
        overrides,
    )
    placed, offices, unplaced, omitted = compile_directory(
        people, load_cache(data / "geocode_cache.json"), overrides, roes
    )
    dhs_people = sum(
        int(item["people"])
        for item in unplaced
        if str(item["reason"]).startswith("Department of Human Services")
    )
    other_people = omitted - dhs_people
    if omitted == 1:
        omitted_note = "1 person on the 2024–2025 log is not in this search."
    else:
        omitted_note = f"{omitted} people on the 2024–2025 log are not in this search."
    if dhs_people == 1:
        omitted_note += (
            " 1 works for the Department of Human Services and is left off the map "
            "unless a school building is known."
        )
    elif dhs_people > 1:
        omitted_note += (
            f" {dhs_people} work for the Department of Human Services and are left off the map "
            "unless a school building is known."
        )
    if other_people == 1:
        omitted_note += " 1 has an employer that could not be matched to a public office."
    elif other_people > 1:
        omitted_note += (
            f" {other_people} have an employer that could not be matched to a public office."
        )
    write_json(data / "illinois_roes.json", {"regions": roes})
    write_json(
        data / "tvis.json",
        {
            "school_year": "2024-2025",
            "omitted_people": omitted,
            "omitted_note": omitted_note,
            "people": placed,
        },
    )
    write_json(data / "entities.json", {"offices": offices})
    write_json(data / "unplaced_employers.json", {"employers": unplaced})
    print(f"people on the working log: {len(people)}")
    print(f"people in the search: {len(placed)}")
    print(f"people omitted: {omitted}")
    print(f"offices: {len(offices)}")
    print(f"unplaced employers: {len(unplaced)}")


if __name__ == "__main__":
    main()
