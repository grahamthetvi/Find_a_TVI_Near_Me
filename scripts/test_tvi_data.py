"""Tests for directory names, ROE labels, matching, and search records."""

from __future__ import annotations

import unittest
from pathlib import Path

from scripts.geocode_entities import address_agrees
from scripts.tvi_data import (
    compile_directory,
    counties_from_note,
    display_name,
    district_numbers,
    employer_office_id,
    employer_roe_label,
    expand_name,
    haversine_miles,
    is_cps,
    is_dhs,
    load_roes,
    location_label,
    match_employer,
    match_school,
    name_key,
    place_key,
    plan_people,
    region_code,
)

ROOT = Path(__file__).resolve().parents[1]
ROES = load_roes(ROOT / "raw_foia" / "illinois_roe_and_county_directory.md")

REGION_CODES = {
    "DU PAGE ROE": "19",
    "Not Found": None,
    "Region 05 North Cook ISC 1": "05",
    "CITY OF CHICAGO": "15",
    "KANE ROE": "31",
    "DE KALB ROE": "16",
    "Region 07 South Cook ISC 4": "07",
    "Adams/Brown/Cass/Morgan/Pike/Scott": "01",
    "LAKE ROE": "34",
    "MC HENRY ROE": "44",
    "BOONE/WINNEBAGO ROE": "04",
    "WILL ROE": "56",
    "Menard/Sangamon": "51",
    "DeWitt/Livingston/Logan/McLean": "17",
    "CHAMPAIGN/FORD ROE": "09",
    "Region 06 West Cook ISC 2": "06",
    "PEORIA ROE": "48",
    "GRUNDY/KENDALL ROE": "24",
    "LaSalle/Marshall/Putnam": "35",
    "CARROLL/JO DAVIESS/STEPHENSON ROE": "08",
    "Lee/Ogle/Whiteside": "47",
    "CLK/CLS/CMBN/DGLAS/EDGR/MLTR/SHLB": "11",
    "ST CLAIR ROE": "50",
    "Mason/Tazewell/Woodford": "53",
    "Error": None,
    "IROQUOIS/KANKAKEE ROE": "32",
    "Franklin/Johnson/Massac/Williamson": "21",
    "VERMILION ROE": "54",
    "MADISON ROE": "41",
    "Alexander/Jackson/Perry/Pulaski/Union": None,
    "ROCK ISLAND ROE": "49",
    "Credential Verified, Region Missing": None,
    "MACON/PIATT ROE": "39",
    "Clinton/Jefferson/Marion/Washington": "13",
    "Bond/Christian/Effingham/Fayette/Montgomery": "03",
    "Edwards/Gallatin/Hamilton/Hardin/Pope/Saline/Wabash/Wayne/White": "20",
    "Henderson/Mercer/Knox/Warren": "33",
    "CLAY/CWFORD/JSPER/LWRNCE/RHLAND": "12",
    "BUREAU/HENRY/STARK ROE": "28",
    "MONROE/RANDOLPH ROE": "45",
    "Fulton/Hancock/McDonough/Schuyler": "26",
}


def lea(name: str, county: str, lat: float = 41.8, lng: float = -88.0) -> dict[str, object]:
    expanded = expand_name(name)
    return {
        "name": name,
        "expanded": expanded,
        "county": county,
        "lat": lat,
        "lng": lng,
        "numbers": district_numbers(expanded),
        "leaid": name,
        "address": "1 Main St",
    }


class RoeTests(unittest.TestCase):
    def test_notes_fill_empty_county_lists(self) -> None:
        self.assertEqual(counties_from_note("Official ISBE jurisdiction: DeKalb County"), ["DeKalb"])
        self.assertEqual(
            counties_from_note(
                "Official ISBE jurisdiction: DeWitt, Livingston, Logan, McLean Counties"
            ),
            ["DeWitt", "Livingston", "Logan", "McLean"],
        )
        self.assertEqual(
            counties_from_note("Official ISBE jurisdiction: Monroe, Randolph Counties"),
            ["Monroe", "Randolph"],
        )
        by_code = {roe["roe_code"]: roe for roe in ROES}
        self.assertEqual(by_code["16"]["counties"], ["DeKalb"])
        self.assertEqual(
            by_code["17"]["counties"], ["DeWitt", "Livingston", "Logan", "McLean"]
        )
        self.assertEqual(by_code["45"]["counties"], ["Monroe", "Randolph"])
        self.assertEqual(by_code["60"]["counties"], [])
        self.assertIsNone(by_code["60"]["label"])
        self.assertEqual(by_code["15"]["label"], "City of Chicago")
        self.assertEqual(by_code["05"]["label"], "North Cook")
        self.assertEqual(by_code["19"]["label"], "DuPage ROE")

    def test_every_logged_region_string(self) -> None:
        for region, expected in REGION_CODES.items():
            with self.subTest(region=region):
                self.assertEqual(region_code(region, ROES), expected)

    def test_cook_stays_split(self) -> None:
        self.assertEqual(
            employer_roe_label("Cook", "Chicago Public Schools District 299", [], ROES),
            "City of Chicago",
        )
        self.assertIsNone(employer_roe_label("Cook", "Some Suburban District", [], ROES))
        self.assertEqual(
            employer_roe_label(
                "Cook",
                "Some Suburban District",
                ["Region 05 North Cook ISC 1"],
                ROES,
            ),
            "North Cook",
        )
        self.assertIsNone(
            employer_roe_label("Cook", "Some Suburban District", ["DU PAGE ROE"], ROES)
        )
        self.assertEqual(employer_roe_label("McLean", "Illinois State University", [], ROES), "DeWitt, Livingston, Logan, and McLean ROE")
        self.assertIsNone(employer_roe_label("Pulaski", "Jamp Spec Educ Services", [], ROES))


class NameTests(unittest.TestCase):
    def test_name_key_keeps_hyphen_and_apostrophe(self) -> None:
        self.assertEqual(name_key("  KAILYN ", "O'DONNELL"), name_key("Kailyn", "O'Donnell"))
        self.assertNotEqual(name_key("Ann", "Smith"), name_key("Anne", "Smith"))

    def test_all_caps_display(self) -> None:
        self.assertEqual(display_name("KAILYN", "O'DONNELL"), "Kailyn O'Donnell")
        self.assertEqual(display_name("ALANA", "MCBRIDE"), "Alana McBride")
        self.assertEqual(display_name("Heidi", "LeRette-Kauffman"), "Heidi LeRette-Kauffman")

    def test_place_keys(self) -> None:
        self.assertEqual(place_key("St. Charles city"), place_key("Saint Charles"))
        self.assertEqual(place_key("DeKalb"), "dekalb")
        self.assertEqual(place_key("La Salle"), "lasalle")
        self.assertEqual(place_key("McHenry"), "mchenry")
        self.assertEqual(place_key("Springfield, Illinois"), "springfield")
        self.assertEqual(place_key("Adair CDP"), "adair")


class MatchTests(unittest.TestCase):
    def test_exact_and_fuzzy_employer_matches(self) -> None:
        offices = [
            lea("SD U-46", "kane"),
            lea("Harlem UD 122", "winnebago"),
            lea("Harlem UD 122", "cook", lat=41.9, lng=-87.7),
            lea("Jasper County CUD 1", "jasper", lat=39.0, lng=-88.2),
            lea("Other CUD 1", "jasper", lat=39.1, lng=-88.3),
            lea("Dept of Human Services", "morgan", lat=39.7, lng=-90.2),
        ]
        u46 = match_employer("School District U-46", "Kane", offices)
        self.assertIsNotNone(u46)
        assert u46 is not None
        self.assertEqual(u46["name"], "SD U-46")
        harlem = match_employer("Harlem School District 122", "Winnebago", offices)
        self.assertIsNotNone(harlem)
        assert harlem is not None
        self.assertEqual(harlem["county"], "winnebago")
        self.assertIsNone(match_employer("Harlem School District 99", "Winnebago", offices))
        self.assertIsNone(match_employer("Dept of Human Services", "Morgan", offices))
        oswego = dict(lea("CUSD 308", "kendall"))
        oswego["city"] = "oswego"
        eastland = dict(lea("Eastland CUSD 308", "carroll", lat=42.1, lng=-89.7))
        eastland["city"] = "shannon"
        matched = match_employer(
            "Oswego Community Unit School Districts 308",
            "Kendall",
            [oswego, eastland],
        )
        self.assertIsNotNone(matched)
        assert matched is not None
        self.assertEqual(matched["name"], "CUSD 308")
        self.assertTrue(is_dhs("Dept of Human Services"))
        self.assertTrue(is_cps("Chicago Public Schools District 299"))
        self.assertFalse(is_cps("Chicago Ridge SD 127-5"))

    def test_school_match_rejects_a_tie(self) -> None:
        exact = {
            "name": "East High School",
            "expanded": expand_name("East High School"),
            "lat": 40.0,
            "lng": -89.0,
        }
        academy = {
            "name": "East High School Academy",
            "expanded": expand_name("East High School Academy"),
            "lat": 40.1,
            "lng": -89.1,
        }
        self.assertEqual(match_school("East High School", [exact, academy]), exact)
        twin = dict(exact)
        twin["lat"] = 41.0
        self.assertIsNone(match_school("East High School", [exact, twin]))


class CompileTests(unittest.TestCase):
    def test_dhs_cps_and_two_points(self) -> None:
        roes = ROES
        current = [
            {"first": "Gina", "last": "Carr", "employer": "Dept of Human Services", "county": "Morgan"},
            {"first": "Ada", "last": "Lovelace", "employer": "Chicago Public Schools District 299", "county": "Cook"},
            {"first": "Grace", "last": "Hopper", "employer": "Springfield SD 186", "county": "Sangamon"},
        ]
        prior = [
            {
                "first": "Ada",
                "last": "Lovelace",
                "region": "CITY OF CHICAGO",
                "district": "City of Chicago SD 299",
                "site": "Curie Metropolitan High School",
            },
            {
                "first": "Grace",
                "last": "Hopper",
                "region": "Menard/Sangamon",
                "district": "Springfield SD 186",
                "site": "Lincoln Elementary School",
            },
        ]
        people = plan_people(current, prior, [], roes, {"phones": {}, "linkedin": {}, "om": {}, "ei": {}})
        by_name = {person["name"]: person for person in people}
        self.assertEqual(by_name["Gina Carr"]["ei"], "Yes")
        self.assertEqual(by_name["Ada Lovelace"]["employers"][0]["roe"], "City of Chicago")
        dhs_id = employer_office_id("Dept of Human Services", "Morgan")
        cps_id = by_name["Ada Lovelace"]["employers"][0]["office_id"]
        school_id = by_name["Ada Lovelace"]["schools"][0]["office_id"]
        grace_office = by_name["Grace Hopper"]["employers"][0]["office_id"]
        grace_school = by_name["Grace Hopper"]["schools"][0]["office_id"]
        cache = {
            dhs_id: {"lat": 39.73, "lng": -90.24, "kind": "district_office", "matched_name": "Dept of Human Services"},
            cps_id: {"lat": 41.88, "lng": -87.63, "kind": "district_office", "matched_name": "Chicago Public Schools Dist 299"},
            school_id: {"lat": 41.80, "lng": -87.70, "kind": "school", "matched_name": "Curie Metropolitan High School"},
            grace_office: {"lat": 39.78, "lng": -89.65, "kind": "district_office", "matched_name": "Springfield SD 186"},
            grace_school: {"lat": 40.10, "lng": -89.00, "kind": "school", "matched_name": "Lincoln Elementary School"},
        }
        placed, offices, unplaced, omitted = compile_directory(
            people, cache, {"phones": {}, "linkedin": {}, "om": {}, "ei": {}}
        )
        names = {person["name"] for person in placed}
        self.assertNotIn("Gina Carr", names)
        self.assertIn("Ada Lovelace", names)
        ada = next(person for person in placed if person["name"] == "Ada Lovelace")
        self.assertEqual(len(ada["locations"]), 1)
        self.assertIn("Curie Metropolitan High School", ada["locations"][0]["label"])
        self.assertNotIn("district office", ada["locations"][0]["label"])
        grace = next(person for person in placed if person["name"] == "Grace Hopper")
        self.assertEqual(len(grace["locations"]), 2)
        self.assertEqual(omitted, 1)
        self.assertTrue(any(item["reason"].startswith("Department of Human Services") for item in unplaced))
        self.assertEqual(len(offices), 4)
        self.assertEqual(
            location_label("Chicago Public Schools District 299", "district office", "City of Chicago"),
            "Chicago Public Schools District 299, district office, City of Chicago",
        )

    def test_same_building_keeps_the_school(self) -> None:
        people = [
            {
                "id": "grace-hopper",
                "name": "Grace Hopper",
                "om": "Not listed",
                "ei": "Not listed",
                "linkedin": "Not listed",
                "employers": [
                    {
                        "office_id": "employer-springfield",
                        "name": "Springfield SD 186",
                        "county": "Sangamon",
                        "roe": "Menard and Sangamon ROE",
                        "is_cps": False,
                        "is_dhs": False,
                    }
                ],
                "schools": [
                    {
                        "office_id": "school-lincoln",
                        "site": "Lincoln Elementary School",
                        "district": "Springfield SD 186",
                        "label_employer": "Springfield SD 186",
                        "roe": "Menard and Sangamon ROE",
                    }
                ],
            }
        ]
        cache = {
            "employer-springfield": {"lat": 39.781, "lng": -89.650, "kind": "district_office"},
            "school-lincoln": {"lat": 39.781, "lng": -89.650, "kind": "school", "matched_name": "Lincoln Elementary School"},
        }
        placed, _offices, _unplaced, omitted = compile_directory(
            people, cache, {"phones": {}, "linkedin": {}, "om": {}, "ei": {}}
        )
        self.assertEqual(omitted, 0)
        self.assertEqual(len(placed[0]["locations"]), 1)
        self.assertIn("Lincoln", placed[0]["locations"][0]["label"])


class GeocoderGuardTests(unittest.TestCase):
    def test_street_side_must_agree(self) -> None:
        self.assertFalse(
            address_agrees(
                "506 S Wright St, Urbana, IL 61801",
                "506 N WRIGHT ST, URBANA, IL, 61801",
            )
        )
        self.assertTrue(
            address_agrees(
                "201 S School St, Normal, IL 61761",
                "201 S SCHOOL ST, NORMAL, IL, 61761",
            )
        )


class OfficeCountyLabelTests(unittest.TestCase):
    def test_school_label_uses_the_building_county(self) -> None:
        people = [
            {
                "id": "darla-pearson",
                "name": "Darla Pearson",
                "om": "Not listed",
                "ei": "Not listed",
                "linkedin": "Not listed",
                "employers": [],
                "schools": [
                    {
                        "office_id": "school-geneseo",
                        "site": "Northside Elem School",
                        "district": "Geneseo CUSD 228",
                        "label_employer": "Geneseo CUSD 228",
                        "roe": "DeKalb ROE",
                    }
                ],
            }
        ]
        cache = {
            "school-geneseo": {
                "lat": 41.45,
                "lng": -90.15,
                "kind": "school",
                "matched_name": "Northside Elem School",
                "county": "henry",
            }
        }
        placed, _offices, _unplaced, _omitted = compile_directory(
            people, cache, {"phones": {}, "linkedin": {}, "om": {}, "ei": {}}, ROES
        )
        self.assertIn("Bureau, Henry, and Stark ROE", placed[0]["locations"][0]["label"])
        self.assertNotIn("DeKalb", placed[0]["locations"][0]["label"])


class DistanceTests(unittest.TestCase):
    def test_one_degree_of_latitude_is_about_69_miles(self) -> None:
        distance = haversine_miles(40.0, -89.0, 41.0, -89.0)
        self.assertGreater(distance, 68.5)
        self.assertLess(distance, 69.5)
        self.assertEqual(haversine_miles(40.0, -89.0, 40.0, -89.0), 0.0)


if __name__ == "__main__":
    unittest.main()
