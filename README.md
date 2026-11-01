# Find a TVI Near Me – Illinois Edition

By Addison Graham. Credited to Lilly Graham.

A free, static GitHub Pages search for the 10 closest Teachers of the Visually Impaired in Illinois. No account, no paid API, and no home addresses or personal phone numbers.

## Source workbooks

Both files are in `raw_foia/`. They are public ISBE FOIA responses. They are complementary layers, not two copies of the same list.

| File | Workbook dates | Sheet | Rows | Columns | Role |
| --- | --- | --- | --- | --- | --- |
| `FOIA_-_BPS_Redacted.xlsx` | Created 10 May 2024, edited 13 May 2024 | `Sheet1` | 638 | First name, last name, district, site | Older file. Serving district and school building. |
| `Teacher_Logs_2024-2025.xlsx` | Created 1 Nov 2026 | `results` | 551 | First name, last name, entity, date of activity, lookup notes, source URL | Current employer file. Replaces the May 2026 holders extract. |

The teacher log has 548 people. 477 of them also appear in the May 2024 file. 144 names are only in the 2024 file, and 71 are only in the teacher log. 375 rows name an employer. 176 rows do not, and those rows have no activity year. Dated employer rows are marked 2026 (319), 2025 (24), 2024 (14), or 2023 (18). Fifteen rows are still Department of Human Services. Lookup notes mark 148 people as “No record” and 26 as ambiguous. 84 rows include a public source URL. The log does not include district, school, phone, O&M, or Early Intervention.

The filename says 2024–2025. Most placed rows are dated 2026. The public edition title can follow the filename. The merge rules below use the teacher log as the employer layer and the May 2024 file as the district and school layer.

## What the site will do

GitHub Pages serves `index.html`, `style.css`, and `app.js` from the repository root.

A visitor types an Illinois ZIP code, city, or street address. The page resolves a ZIP or city from `data/il_locations.json` on the visitor’s computer. A street address that includes a house number falls back to the keyless U.S. Census geocoder, then to the city or ZIP in that same address if the census request fails. The page ranks educators with the haversine formula and shows 10 rows.

The page shows employer, distance, LinkedIn, front-office phone, name, O&M, and Early Intervention. Missing enrichment is the words “Not listed”, “Yes”, or “No”. It is never a blank cell or a color-only mark.

People with no located employer stay in `data/tvis.json` and stay out of the distance search.

## Data the page is allowed to publish

`scripts/build_data.py` will merge the two workbooks into minified `data/entities.json` and `data/tvis.json`.

- Match people on first and last name, after trimming whitespace and fixing all-caps names. Keep hyphens and apostrophes.
- Drop a `NULL` employer row when that person has a real employer in either file.
- Keep a person who is `NULL` in both files, with an empty employer list.
- When the teacher log names an employer and the 2024 file names a district or school for the same person, store both on one employer record.
- When one person has two schools or two employer rows, store both, and search by the closer one so the person appears once.
- Keep the activity year, lookup note, and source URL on the employer record. A “No record” or ambiguous note does not invent an employer. The source URL is a public lookup link, and it is not a LinkedIn profile.
- A Department of Human Services row sets Early Intervention to yes. Keep a school assignment from the 2024 file when that person has one.
- Optional `enrichment_overrides.csv` may add a checked public LinkedIn URL, a front-office phone, or an O&M flag. The script must not wipe those on the next build.
- Coordinates are the public school or district office, from the Census gazetteer or the Census geocoder. Cache them. Do not invent a coordinate. Leave it empty until it is checked.
- Never store a home address or a personal phone number.

`robots.txt` will ask crawlers not to index `data/`. The page itself renders only 10 rows. The full relational files remain in this public repository because the underlying records are public FOIA data.

## Accessibility

WCAG 2.1 AA. One skip link, landmarks, and a single heading path from the title to the search and the results. Every control has a visible label. Results are a table with a caption and a row header. A polite live region announces the search. Body text stays at least 18px, targets at least 44px, and the layout reflows at 400% zoom. A control switches between a light theme and a black background with yellow and white text. Focus is a 3px outline.

## Build order

1. `scripts/build_data.py` writes `entities.json`, `tvis.json`, and `il_locations.json` from `raw_foia/`.
2. `scripts/geocode_entities.py` fills coordinates and keeps a cache. Phones stay empty until an override file supplies a checked front-office number.
3. Build the page, the stylesheet, and the search script.
4. Check keyboard use, both themes, and the live announcement.
5. Push `main` and serve GitHub Pages from the repository root.
