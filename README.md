# Find a TVI Near Me – Illinois Edition

By Addison Graham. Credited to Lilly Graham.

A free, static GitHub Pages search for the 10 closest Teachers of the Visually Impaired in Illinois. No account, no paid API, and no home addresses or personal phone numbers.

## Source workbooks

Both files are in `raw_foia/`. They are public ISBE FOIA responses. They are complementary layers, not two copies of the same list.

| File | Workbook dates | Sheet | Rows | Columns | Role |
| --- | --- | --- | --- | --- | --- |
| `FOIA_-_BPS_Redacted.xlsx` | Created 10 May 2024, edited 13 May 2024 | `Sheet1` | 638 | First name, last name, district, site | Older file. Serving district and school building. |
| `FOIA_-_BPS_Holders_Redacted.xlsx` | Created 4 May 2026, edited 7 May 2026 | `results` | 950 | First name, last name, entity | Newer file. Employing district or special-education cooperative. Includes 15 Department of Human Services rows. 631 rows have no entity. |

565 names appear in both files. The May 2026 file does not include district, school, region, phone, O&M, or EI. Those last three fields are not in either workbook.

The site title in the working plan says 2024–2025. Neither workbook is dated in that school year. The public title stays unsettled until the edition year is chosen. The merge rules below do not depend on that title.

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
- When the 2026 file names a cooperative and the 2024 file names a district or school for the same person, store both on one employer record.
- When one person has two schools, store both, and search by the closer one so the person appears once.
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
