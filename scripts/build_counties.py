"""Write Illinois county shapes from the Census cartographic boundary file."""

from __future__ import annotations

import struct
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.downloads import download
from scripts.tvi_data import write_json

COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_20m.zip"
ILLINOIS_STATEFP = "17"
SHAPE_POLYGON = 5


def _dbf_rows(raw: bytes) -> list[dict[str, str]]:
    header_len = struct.unpack_from("<H", raw, 8)[0]
    rec_len = struct.unpack_from("<H", raw, 10)[0]
    fields: list[tuple[str, int]] = []
    offset = 32
    while offset < header_len and raw[offset] not in (0x0D, 0x00):
        name = raw[offset : offset + 11].split(b"\0", 1)[0].decode("ascii")
        length = raw[offset + 16]
        fields.append((name, length))
        offset += 32
    records: list[dict[str, str]] = []
    pos = header_len
    while pos + rec_len <= len(raw):
        if raw[pos] != 0x2A:
            cursor = pos + 1
            row: dict[str, str] = {}
            for name, length in fields:
                row[name] = raw[cursor : cursor + length].decode("latin-1").strip()
                cursor += length
            records.append(row)
        pos += rec_len
    return records


def _close_ring(ring: list[list[float]]) -> list[list[float]]:
    if len(ring) >= 2 and ring[0] != ring[-1]:
        return ring + [ring[0]]
    return ring


def _shp_polygons(raw: bytes) -> list[dict[str, object] | None]:
    shapes: list[dict[str, object] | None] = []
    pos = 100
    while pos + 8 <= len(raw):
        _record, content_len = struct.unpack_from(">2i", raw, pos)
        pos += 8
        body = raw[pos : pos + content_len * 2]
        pos += content_len * 2
        if len(body) < 4:
            shapes.append(None)
            continue
        shape_type = struct.unpack_from("<i", body, 0)[0]
        if shape_type == 0:
            shapes.append(None)
            continue
        if shape_type != SHAPE_POLYGON:
            raise ValueError(f"Unsupported shapefile type {shape_type}")
        nparts, npoints = struct.unpack_from("<2i", body, 36)
        parts = struct.unpack_from(f"<{nparts}i", body, 44)
        points_off = 44 + nparts * 4
        points = [
            list(struct.unpack_from("<2d", body, points_off + index * 16))
            for index in range(npoints)
        ]
        rings = []
        for index, start in enumerate(parts):
            end = parts[index + 1] if index + 1 < nparts else npoints
            rings.append(_close_ring(points[start:end]))
        shapes.append({"type": "Polygon", "coordinates": rings})
    return shapes


def illinois_counties(dbf_raw: bytes, shp_raw: bytes) -> dict[str, object]:
    rows = _dbf_rows(dbf_raw)
    shapes = _shp_polygons(shp_raw)
    if len(rows) != len(shapes):
        raise ValueError("County shapefile tables do not line up.")
    features = []
    for row, geometry in zip(rows, shapes):
        if row.get("STATEFP") != ILLINOIS_STATEFP or geometry is None:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "name": row.get("NAME") or "",
                    "geoid": row.get("GEOID") or "",
                },
                "geometry": geometry,
            }
        )
    features.sort(key=lambda item: str(item["properties"]["name"]))
    if len(features) != 102:
        raise ValueError(f"Expected 102 Illinois counties, found {len(features)}.")
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    source = ROOT / "data" / "source"
    archive_path = source / "cb_2023_us_county_20m.zip"
    if not archive_path.exists():
        download(COUNTY_URL, archive_path)
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        dbf_name = next(name for name in names if name.lower().endswith(".dbf"))
        shp_name = next(name for name in names if name.lower().endswith(".shp"))
        collection = illinois_counties(archive.read(dbf_name), archive.read(shp_name))
    write_json(ROOT / "data" / "il_counties.json", collection)
    print("counties: 102")


if __name__ == "__main__":
    main()
