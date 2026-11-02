# Find a TVI Near Me – Illinois Edition

By Addison Graham. Credited to Lilly Graham.

A static search for the ten Teachers of the Visually Impaired whose public Illinois offices are closest to a city, ZIP code, or street address. Open `index.html`. No account and no paid API.

## Website

The visitor enters an Illinois city, ZIP code, or street address. A city or ZIP is resolved in the browser from `data/il_locations.json`, including a ZIP or city written inside a longer query. A street address is also sent to the Census geocoder. That service does not allow a web page to call it, so a failed street lookup uses the ZIP code or city in the same address. The page ranks offices with the haversine formula and shows ten rows.

Distance is to a public employer office, never to a home and never to the center of a county. The Regional Office of Education is a label on the row. Cook stays split: City of Chicago, North Cook, West Cook, and South Cook. Chicago Public Schools uses a 2023–2024 school building when that building matches, and otherwise says “district office.” A cooperative office may not be the town where an itinerant teacher sees students.

The search is built from the `results` sheet of `Teacher_Logs_2024-2025.xlsx`. The 2023–2024 combined sheet adds a district, school, and region when the same first and last name is there. A name on the COMS lookup sheet sets O&M to Yes. Everyone else is “Not listed.” The reference workbook and every Hold or Removed sheet stay out.

Of 379 people on the working log, 366 are in the search. Thirteen are left out: twelve Department of Human Services rows, which are not placed on a single office unless a school building is known, and one Echo Joint Agreement row, which did not match a public office. `data/unplaced_employers.json` lists those employers. `data/overrides.json` can add a checked front-office phone or a public profile. The build reads that file and does not rewrite it.

`robots.txt` asks crawlers to skip `data/`. The workbooks are already in this public repository, so that file does not hide them.

GitHub Pages serves the repository root: `index.html`, `style.css`, `app.js`, and `data/`. In the repository settings, set Pages to deploy from the branch root.

Rebuild from the repository root after `pip install -r requirements.txt`:

```bash
python3 scripts/build_locations.py
python3 scripts/geocode_entities.py
python3 scripts/build_data.py
python3 -m unittest scripts.test_tvi_data
node --test tests/search.test.mjs
```

`.github/workflows/test.yml` runs those two commands on every push and pull request. The rebuild and lookup scripts stay off that workflow: the rebuild downloads public location files, and the lookup scripts write back into a workbook.

`build_locations.py` reads the Census place and ZCTA gazetteers. `geocode_entities.py` reads the NCES EDGE 2023–24 district and school files, the IPEDS directory for three universities, and the Census geocoder for two state campuses. It writes `data/geocode_cache.json` and does not invent a coordinate. `build_data.py` writes `data/illinois_roes.json`, `data/entities.json`, and `data/tvis.json`.

## What is in the repository

| Path | Role |
| --- | --- |
| `index.html`, `style.css`, `app.js`, `search.js` | The search page. |
| `data/tvis.json` | People in the search, with the office used for each row. |
| `data/entities.json` | Public offices and their coordinates. |
| `data/il_locations.json` | Illinois cities and ZIP code points. |
| `data/illinois_roes.json` | Region codes, labels, and counties. Codes 16, 17, and 45 are filled from their notes. |
| `data/geocode_cache.json` | Cached public coordinates. |
| `data/overrides.json` | Optional checked phone numbers and public profiles. |
| `data/unplaced_employers.json` | Employers left out of the radius. |
| `raw_foia/*.xlsx` | Source workbooks. Location lives in county, ROE/region, employer, district, and school-site columns. |
| `raw_foia/illinois_roe_and_county_directory.md` | JSON crosswalk of 40 ISBE region codes to counties. The extension is `.md`; the body is a JSON array. |
| `scripts/build_locations.py` | Builds the city and ZIP file. |
| `scripts/geocode_entities.py` | Matches offices to public coordinates. |
| `scripts/build_data.py` | Builds the search files. |
| `scripts/lookup_null_employers.py` | Fills blank employers in the 2024–2025 log from public Illinois salary pages. |
| `scripts/lookup_isbe_roe.py` | Appends an ISBE registration region to the lookup notes of blank-employer rows in that same log. |
| `LICENSE` | MIT, copyright 2026 Addison Graham. |

The build scripts and the two lookup scripts need Python 3 and `openpyxl` (`requirements.txt`). The lookup scripts call the public internet and save changes back into `raw_foia/Teacher_Logs_2024-2025.xlsx`.

## Workbooks

Row counts below are non-empty data rows. Blank means empty, `NULL`, or `NA`.

| File | Sheet | Rows | Location fields |
| --- | --- | --- | --- |
| `Teacher_Logs_2024-2025.xlsx` | `results` | 381 | `Entity Name`, `County`. No ROE, city, ZIP, street, or coordinates. |
| `Teacher_Logs_2024-2025.xlsx` | `Hold - pension and school` | 9 | `Entity Name`, `County` (8 Cook, 1 DuPage). |
| `Teacher_Logs_2024-2025.xlsx` | `Removed - retired or expired` | 2 | `Entity Name`. `County` is blank on both rows. |
| `Teacher_Logs_2023-2024.xlsx` | `Combined` | 538 | `Region`, `District`, `Site`. No county, city, ZIP, street, or coordinates. |
| `Teacher_Logs_2023-2024.xlsx` | `Summary` | 5 | Counts only. |
| `Teacher_Logs_2023-2024.xlsx` | `Removed (pre-2022)` | 81 | `Region`, `District`, `Site`. |
| `Teacher_Logs_2023-2024.xlsx` | `Hold - pension and school` | 9 | `Region`, `District`, `Site`. |
| `Teacher_Logs_2023-2024.xlsx` | `Removed - retired or expired` | 9 | `Region`, `District`, `Site`. |
| `2024-2025 Active Licenses, No Confirmed Employer.xlsx` | `Retired but still active` | 152 | `Entity Name` is `NULL` on every row. The only geography is an `ISBE ROE:` sentence inside `Lookup Notes`. |
| `2024-2025 Active Licenses, No Confirmed Employer.xlsx` | `Removed - retired or expired` | 1 | Same columns. |
| `Illinois_COMS_govsalaries.xlsx` | `COMS lookup` | 140 | `2024-2025 county`, `2024-2025 employer`, `2023-2024 district`, `2023-2024 site`. |
| `Illinois_CATIS_govsalaries.xlsx` | `CATIS lookup` | 12 | Same county, employer, district, and site columns as the COMS sheet. |
| `Illinois_CLVT_govsalaries.xlsx` | `CLVT lookup` | 20 | `Employer` only. No county, ROE, or city column. |
| `Illinois_CVRT_govsalaries.xlsx` | `IL CVRTs` | 41 | `State` (all `IL`), `Employer`, `Employer Type`. No county, ROE, or city column. |

The COMS, CATIS, CLVT, and CVRT workbooks also have small hold and removed sheets. Those sheets repeat the same location columns as the lookup sheet they came from.

`Teacher_Logs_2023-2024.xlsx` `Summary` matches a recount of `Combined`: Match 478, District filled from File 2 50, Only in File 1 10. It also records 81 removed pre-2022 rows and 201 kept rows with no date. Those 201 undated rows are the same 201 rows whose `District` is blank.

## How place names are written

The current employer log (`results`) stores one county on every row. All 381 counties are filled. There are 50 distinct spellings, and the spellings are stable inside this sheet: `DuPage`, `DeKalb`, `LaSalle`, `St. Clair`, `McHenry`, `McLean`, `Jo Daviess`. Each employer string on this sheet has one county, except two people who have two rows:

- Heidi LeRette-Kauffman: Northwestern Illinois Assn / DeKalb, and CUSD 300 / Kane.
- Morgan Hendon: Evanston CCSD 65 / Cook, and Evanston Dists 65/202 Jnt Agr / Cook.

The 2023–2024 log stores an ISBE region, a district, and a school site. All 538 `Region` values are filled. There are 41 distinct strings. `District` is blank on 201 rows. `Site` is blank on 338 rows. A filled site is a school building name (175 distinct names). No site equals a county name, and none is a street address.

The active-license sheet has no county. All 152 notes contain `ISBE ROE:`. Parsed as written: 124 notes name one region, 22 name more than one, and 6 say there is no registered region.

The credential sheets borrow the 2024–2025 county when the person is on that log. They do not add a city.

Nothing in the repository has a ZIP code, a street address, a latitude, or a longitude.

## Counties, ROEs, and cities

Names were compared after trimming and case-folding. People were joined on first name plus last name, case-folded, with internal spaces collapsed. That join does not merge nicknames or swapped middle names.

### Counties

On `results`, 290 rows (48 county names) sit in exactly one directory ROE once the notes on directory codes 16 and 17 are read as the county list. `Cook` is 90 rows and 89 people, and the directory splits Cook four ways (regions 05, 06, 07, and 15). `Pulaski` is 1 row (Gina Hill, Jamp Spec Educ Services) and is not in the directory.

`COMS lookup` has a county on 60 rows and a blank county on 80. The 60 filled values match the 2024–2025 log for the same person, including the one multi-county cell `DeKalb; Kane`. The sheet’s `In 2024-2025 log` flag matches that name join (60 Yes, 80 No).

`CATIS lookup` has a county on 3 rows and a blank on 9. The 3 filled values match the 2024–2025 log.

### ROEs

The directory has 40 entries. Use the `counties` array, not `raw_value`, when the two disagree:

| Code | `raw_value` spelling | County list |
| --- | --- | --- |
| 08 | Carrol | Carroll |
| 09 | Champain | Champaign |
| 11 | Edger | Edgar |
| 26 | Hancook | Hancock |
| 35 | Lasalle | LaSalle |

Codes 16, 17, and 45 have an empty `counties` array. The note on each row names the counties: DeKalb; DeWitt, Livingston, Logan, and McLean; Monroe and Randolph. Code 60 is `NA` and has no counties. The directory does not list Alexander, Pulaski, or Union. Region 30 is only Jackson and Perry.

Of the 538 combined-sheet regions, 469 match one directory code after those notes are applied. Matching ignores the `ROE` suffix, county order, and the abbreviations already in the sheet (`DU PAGE`, `DE KALB`, `MC HENRY`, `ST CLAIR`, `CLK/CLS/CMBN/DGLAS/EDGR/MLTR/SHLB`, `CLAY/CWFORD/JSPER/LWRNCE/RHLAND`, and the Cook ISC labels). Another 66 values are not regions: `Not Found` 57, `Error` 6, `Credential Verified, Region Missing` 3. The last 3 are `Alexander/Jackson/Perry/Pulaski/Union`, which is wider than directory region 30.

`CITY OF CHICAGO` (40 combined rows) is directory code 15. It is a finer place than the county value `Cook`.

### The two teacher logs joined

`results` has 379 people (381 rows). `Combined` has 522 people (538 rows). The same name is on both sheets for 330 people. 49 people are only on the current log. 192 are only on the 2023–2024 log.

For those 330 people, the current county was checked against the counties of the 2023–2024 region:

| Result | People |
| --- | --- |
| County is the only county in that ROE | 117 |
| County is one member of a multi-county ROE | 71 |
| County is Cook, and the older region is one Cook subregion | 64 |
| Older region is only `Not Found`, `Error`, or `Credential Verified, Region Missing` | 36 |
| County is outside the older region | 42 |

The 64 Cook agreements still lose the subregion, because the current sheet only says `Cook`.

The 42 disagreements split three ways:

- 9 people have the same employer on both sheets, and the county still falls outside the region. Six of those nine are coded `DU PAGE ROE` beside an employer outside DuPage: Shelbyville CUSD 4 (Shelby), Kirby School District 140 (Cook), Illinois State University (McLean), Sangamon Area Special Education District (Sangamon), University of Illinois at Urbana-Champaign (Champaign), and Valley View CUSD 365U (Will). The other three are Kaneland CUSD 302 (Kane county, `LAKE ROE`), Eastern Illinois Area Special Education (Coles county, Bond/Christian/Effingham/Fayette/Montgomery), and Jamp Spec Educ Services (Pulaski county, Franklin/Johnson/Massac/Williamson).
- 20 people have a different employer on each sheet. The county and the region describe different jobs.
- 13 people have a region and no district on the older sheet, so the region cannot be checked against a school.

Employer strings for the same district are not normalized. The current log uses both short and long forms (`SD U-46` and `School District U-46`, `Springfield SD 186` and `Springfield School District 186`, `City of Chicago SD 299` on the older sheet and `Chicago Public Schools District 299` on the current one, `Harlem UD 122` and `Harlem School District 122`). A district number is not a safe join key. The same number belongs to different districts (`CUSD 1`, district 122, district 204, and others).

### Cities

There is no city column. The only city that can be read off the sheets is Chicago:

- 24 current-log rows, all county Cook, name `Chicago Public Schools District 299`.
- 19 of those people are `CITY OF CHICAGO` on the 2023–2024 log, 3 are `Not Found`, and 2 are absent from that log.
- The older log has 40 `CITY OF CHICAGO` rows and 25 `City of Chicago SD 299` district rows.

School sites sometimes contain a place word (`Batavia Sr High School`, `Kankakee Junior High School`). The repository has no list that separates those place words from the rest of the building name.

### Other sheets

Active licenses, joined by the same name rule: 126 of 152 people are also on the 2023–2024 log, and none are on the current `results` sheet. For 104 of those 126, the ROE in the note shares a directory code with the 2023–2024 region. One note conflicts with that region (Deborah Faynik: `GRUNDY/KENDALL ROE` in the note, `Region 07 South Cook ISC 4` on the older log). Six notes name no region while the older log has one. Fifteen older-log rows for this group are themselves `Not Found`, `Error`, or `Credential Verified, Region Missing`. Twenty-six active-license people are on neither teacher log.

Of the 124 single-region active-license notes: 48 are a one-county ROE, 15 are `CITY OF CHICAGO`, 14 are a suburban Cook ISC, and 47 are a multi-county ROE.

CLVT has an employer on 6 of 20 lookup rows and a blank employer on 14. One CLVT name is on the 2023–2024 log. None are on the current log. CVRT has an employer on 8 of 41 rows and a blank employer on 33. `State` is `IL` on all 41. Four CVRT names appear on a teacher log. Those name hits are too few, and the employer wording often differs (`Dept of Human Services` versus `Illinois Department of Human Services`), so the credential sheets do not inherit a county by themselves.

## What can be filled from this repository

Deterministic, using columns and the directory already here:

- Map 469 of 538 older-log region strings onto one directory code, using the county-list notes for codes 16, 17, and 45.
- From the current log, assign one ROE to 290 of 381 rows. Leave Cook (90 rows) and Pulaski (1 row) unassigned.
- Set city to Chicago on the 24 Chicago Public Schools rows, and treat them as directory code 15.
- On the active-license sheet, assign a single county to the 48 one-county ROE notes, and assign Cook plus Chicago to the 15 `CITY OF CHICAGO` notes. The 14 suburban Cook notes yield Cook only.
- Keep the 60 COMS counties and 3 CATIS counties as they are. They already match the current log.

Approximate, with an assumption and leftover error:

- Treat the current-log county as the employer’s office county. That is a poor stand-in for where an itinerant teacher works. A cooperative-style employer name appears on 111 of 381 rows. All 24 Northwestern Illinois Assn rows are DeKalb; of the 20 of those people who are also on the older log, only 8 are `DE KALB ROE`. All 12 `Dept of Human Services` rows are Morgan, the same county as the two Illinois School for the Visually Impaired rows. The sheets do not say which building or caseload that Morgan code refers to.
- Where the same person agrees across the two logs (252 people), the older region and the current county can be stored together. For the 64 Cook agreements, copying the older Cook subregion forward assumes the registration still matches the newer employer.
- For the 117 older-log rows that have a single-county ROE and no district, the county can be set to that ROE’s county. That is a registration county. It is not a school, and it is not a city.
- For the 20 disagreements that are different employers, keep both records and label them with their own years. Do not collapse them.
- Two COMS rows and one CATIS row have a blank county and a 2023–2024 single-county ROE, so that one county can be copied. A suburban Cook ISC copies as Cook only.

Cannot be filled from the workbooks alone. The website build, described above, adds office coordinates from NCES and the Census geocoder. These still cannot be filled from the sheets themselves:

- A city, ZIP, street, or coordinate for anyone except the Chicago rows named above. No sheet and no script contains a gazetteer or a geocode cache.
- A Cook subregion for current-log employers other than Chicago Public Schools when the older log does not supply one. Of the non-Chicago Cook people, 5 have a non-Cook region, 5 are `Not Found`, and 10 are not on the older log.
- One county for a multi-county ROE (47 single-region active-license notes, 22 multi-region notes, 53 older-log rows with a multi-county region and no district, and 2 of the blank COMS counties).
- An ROE for Pulaski, or for the 3 older-log rows labeled `Alexander/Jackson/Perry/Pulaski/Union`.
- A location for the remaining blank credential rows: 75 COMS counties with no 2023–2024 row, 1 COMS county whose older region is not an ROE, 8 CATIS counties with no 2023–2024 row, 14 blank CLVT employers, and 33 blank CVRT employers. The lookup scripts search salary sites and the ISBE educator inquiry. They do not return a city or a coordinate, and the current `results` sheet no longer has blank employers for them to fill.

The nine same-employer conflicts cannot be settled from these files. Both values are present and they disagree.

## Lookup scripts

From the repository root, with `openpyxl` installed:

```bash
python3 scripts/lookup_null_employers.py
python3 scripts/lookup_isbe_roe.py
```

`lookup_null_employers.py` reads `raw_foia/Teacher_Logs_2024-2025.xlsx`, searches govsalaries.com for rows whose entity is blank or `NULL`, and writes the employer, year, note, and source URL back into that workbook. It also writes `/tmp/tvi_null_lookup.json`. It does not store salary amounts.

`lookup_isbe_roe.py` reads the same workbook, asks the public ISBE educator inquiry for a region on those blank-entity rows, and appends `ISBE ROE:` to the lookup note. It also writes `/tmp/tvi_isbe_roe.json`.

On the current `results` sheet every entity is filled, so a new run finds no blank rows to update. The blank employers now live in `2024-2025 Active Licenses, No Confirmed Employer.xlsx`, which neither script opens. Both scripts still save the 2024–2025 workbook if they are run. Run them only when you intend to refresh that file from the public sites.
