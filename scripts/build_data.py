"""Write the ROE list, office file, and teacher file the page searches."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.sources import (
    load_catis,
    load_clvt,
    load_coms,
    load_current,
    load_cvrt,
    load_prior,
)
from scripts.tvi_data import (
    YEAR_CURRENT,
    compile_directory,
    load_overrides,
    load_roes,
    plan_people,
    write_json,
)


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
        load_catis(raw / "Illinois_CATIS_govsalaries.xlsx"),
        load_clvt(raw / "Illinois_CLVT_govsalaries.xlsx"),
        load_cvrt(raw / "Illinois_CVRT_govsalaries.xlsx"),
    )
    placed, offices, unplaced, stats = compile_directory(
        people, load_cache(data / "geocode_cache.json"), overrides, roes
    )
    current_stats = stats[YEAR_CURRENT]
    write_json(data / "illinois_roes.json", {"regions": roes})
    write_json(
        data / "tvis.json",
        {
            "school_year": YEAR_CURRENT,
            "omitted_people": current_stats["omitted_people"],
            "omitted_note": current_stats["omitted_note"],
            "years": stats,
            "people": placed,
        },
    )
    write_json(data / "entities.json", {"offices": offices})
    write_json(data / "unplaced.json", {"people": unplaced})
    print(f"people planned: {len(people)}")
    print(f"people in the search: {len(placed)}")
    for year, year_stats in stats.items():
        print(f"{year} omitted: {year_stats['omitted_people']}")
    print(f"offices: {len(offices)}")
    print(f"unplaced people: {len(unplaced)}")


if __name__ == "__main__":
    main()
