"""Build Illinois place and ZIP points from the Census gazetteer."""

from __future__ import annotations

import csv
import io
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.downloads import download
from scripts.tvi_data import bare_place_name, place_key, write_json

PLACE_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2026_Gazetteer/2026_gaz_place_17.txt"
)
ZCTA_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2026_Gazetteer/2026_Gaz_zcta_national.zip"
)
RELATION_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/"
    "tab20_zcta520_county20_natl.txt"
)


def _text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode("utf-8", errors="replace")


def _rows(text: str) -> list[dict[str, str]]:
    sample = text.splitlines()[0]
    delimiter = "|" if sample.count("|") >= sample.count("\t") else "\t"
    return list(csv.DictReader(io.StringIO(text), delimiter=delimiter))


def _column(row: dict[str, str], *names: str) -> str:
    folded = {key.strip().casefold(): value for key, value in row.items() if key}
    for name in names:
        if name.casefold() in folded and folded[name.casefold()] is not None:
            return str(folded[name.casefold()]).strip()
    return ""


def _float(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def illinois_zips(relation_text: str) -> set[str]:
    zips: set[str] = set()
    for row in _rows(relation_text):
        zcta = _column(row, "GEOID_ZCTA5_20", "ZCTA5", "GEOID_ZCTA5")
        county = _column(row, "GEOID_COUNTY_20", "GEOID_COUNTY")
        if zcta and county.startswith("17"):
            zips.add(zcta.zfill(5))
    if not zips:
        raise ValueError("The ZCTA relationship file did not list any Illinois counties.")
    return zips


def places_from_gazetteer(text: str) -> list[dict[str, object]]:
    places = []
    for row in _rows(text):
        name = _column(row, "NAME")
        lat = _float(_column(row, "INTPTLAT"))
        lng = _float(_column(row, "INTPTLONG"))
        if not name or lat is None or lng is None:
            continue
        key = place_key(name)
        if not key:
            continue
        places.append({"name": bare_place_name(name), "key": key, "lat": lat, "lng": lng})
    places.sort(key=lambda item: (str(item["name"]), float(item["lat"])))
    return places


def zips_from_gazetteer(text: str, illinois: set[str]) -> dict[str, dict[str, float]]:
    zips: dict[str, dict[str, float]] = {}
    for row in _rows(text):
        geoid = _column(row, "GEOID", "GEOID_ZCTA5").zfill(5)
        if geoid not in illinois:
            continue
        lat = _float(_column(row, "INTPTLAT"))
        lng = _float(_column(row, "INTPTLONG"))
        if lat is None or lng is None:
            continue
        zips[geoid] = {"lat": lat, "lng": lng}
    return zips


def _zcta_text(path: Path) -> str:
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if name.endswith(".txt")]
            if not names:
                raise ValueError(f"No text file inside {path}")
            return archive.read(names[0]).decode("utf-8", errors="replace")
    return _text(path)


def main() -> None:
    source = ROOT / "data" / "source"
    place_path = source / "2026_gaz_place_17.txt"
    zcta_path = source / "2026_Gaz_zcta_national.zip"
    relation_path = source / "tab20_zcta520_county20_natl.txt"
    if not place_path.exists():
        download(PLACE_URL, place_path)
    if not zcta_path.exists():
        download(ZCTA_URL, zcta_path)
    if not relation_path.exists():
        download(RELATION_URL, relation_path)
    illinois = illinois_zips(_text(relation_path))
    places = places_from_gazetteer(_text(place_path))
    zips = zips_from_gazetteer(_zcta_text(zcta_path), illinois)
    write_json(ROOT / "data" / "il_locations.json", {"places": places, "zips": zips})
    print(f"places: {len(places)}")
    print(f"zips: {len(zips)}")


if __name__ == "__main__":
    main()
