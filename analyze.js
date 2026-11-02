import {
  DEFAULT_YEAR,
  ROLE_LABELS,
  ROLE_ORDER,
  SCHOOL_YEARS,
  countyKey,
  indexOffices,
  locateQuery,
  locationsForYear,
  nearestPeople,
  personMatchesRoles,
} from "./search.js";
import { countColor, featureBounds, geometryPath } from "./map.js";

const filters = document.querySelector("#filters");
const yearInputs = [...document.querySelectorAll('#filters input[name="year"]')];
const roleInputs = ROLE_ORDER.map((role) =>
  document.querySelector(`#filters input[name="roles"][value="${role}"]`),
).filter(Boolean);
const themeButton = document.querySelector("#theme");
const status = document.querySelector("#status");
const stats = document.querySelector("#stats");
const mapWrap = document.querySelector("#map");
const mapLegend = document.querySelector("#map-legend");
const countyDetail = document.querySelector("#county-detail");
const countyRows = document.querySelector("#county-rows");
const roeRows = document.querySelector("#roe-rows");
const compareStats = document.querySelector("#compare-stats");
const compareRows = document.querySelector("#compare-rows");
const placeForm = document.querySelector("#place-form");
const placeInput = document.querySelector("#place-q");
const placeSummary = document.querySelector("#place-summary");
const unplacedGroups = document.querySelector("#unplaced-groups");
const root = document.documentElement;

const THEME_KEY = "tvi-theme";
const MAP_WIDTH = 560;
const MAP_HEIGHT = 880;

/** @type {{people: Array<object>} | null} */
let directory = null;
/** @type {Map<string, object> | null} */
let offices = null;
/** @type {{places: Array<object>, zips: Record<string, {lat: number, lng: number}>} | null} */
let places = null;
/** @type {{people: Array<{id: string, name: string, roles: string[], year: string, reason: string}>} | null} */
let unplaced = null;
/** @type {{features: Array<object>} | null} */
let counties = null;
/** @type {{regions: Array<{roe_code: string, label: string, counties: string[]}>} | null} */
let roes = null;
let selectedCounty = "";

function setTheme(contrast) {
  root.dataset.theme = contrast ? "contrast" : "light";
  themeButton.setAttribute("aria-pressed", contrast ? "true" : "false");
  themeButton.textContent = contrast ? "Light theme" : "Black and yellow theme";
  try {
    localStorage.setItem(THEME_KEY, contrast ? "contrast" : "light");
  } catch {
    /* The theme still changes for this visit when storage is blocked. */
  }
}

function storedContrast() {
  try {
    return localStorage.getItem(THEME_KEY) === "contrast";
  } catch {
    return false;
  }
}

setTheme(storedContrast());
themeButton.addEventListener("click", () => {
  setTheme(root.dataset.theme !== "contrast");
  render();
});

/**
 * @param {string} url
 */
async function loadJson(url) {
  const response = await fetch(new URL(url, import.meta.url));
  if (!response.ok) {
    throw new Error(url);
  }
  return response.json();
}

function selectedYears() {
  const checked = yearInputs.find((input) => input.checked);
  const value = checked ? checked.value : DEFAULT_YEAR;
  if (value === "both") {
    return [...SCHOOL_YEARS];
  }
  return [value];
}

function selectedRoles() {
  return roleInputs.filter((input) => input.checked).map((input) => input.value);
}

function announce(message) {
  status.textContent = message;
  status.focus();
}

/**
 * @param {string} label
 * @param {string | number} value
 */
function statCard(label, value) {
  const item = document.createElement("div");
  item.className = "stat";
  const number = document.createElement("p");
  number.className = "value";
  number.textContent = String(value);
  const caption = document.createElement("p");
  caption.textContent = label;
  item.append(number, caption);
  return item;
}

function fillTable(body, rows) {
  body.replaceChildren();
  for (const cells of rows) {
    const tr = document.createElement("tr");
    cells.forEach((value, index) => {
      const cell = document.createElement(index === 0 ? "th" : "td");
      if (index === 0) {
        cell.scope = "row";
      }
      cell.textContent = String(value);
      tr.append(cell);
    });
    body.append(tr);
  }
}

/**
 * @param {string[]} years
 * @param {string[]} roles
 */
function coverage(years, roles) {
  /** @type {Map<string, {person: object, offices: Map<string, {office: object, loc: object}>}>} */
  const people = new Map();
  /** @type {Map<string, {name: string, people: Set<string>, offices: Set<string>}>} */
  const byCounty = new Map();
  /** @type {Map<string, {people: Set<string>, offices: Set<string>}>} */
  const byRoe = new Map();
  const officeIds = new Set();

  if (!directory || !offices) {
    return { people, byCounty, byRoe, officeIds };
  }

  for (const person of directory.people) {
    if (!personMatchesRoles(person, roles)) {
      continue;
    }
    for (const year of years) {
      for (const loc of locationsForYear(person, year)) {
        const office = offices.get(loc.office_id);
        if (!office) {
          continue;
        }
        officeIds.add(office.id);
        let record = people.get(person.id);
        if (!record) {
          record = { person, offices: new Map() };
          people.set(person.id, record);
        }
        record.offices.set(office.id, { office, loc });
        const county = countyKey(office.county);
        if (county) {
          let countyRow = byCounty.get(county);
          if (!countyRow) {
            countyRow = { name: office.county, people: new Set(), offices: new Set() };
            byCounty.set(county, countyRow);
          }
          countyRow.people.add(person.id);
          countyRow.offices.add(office.id);
        }
        const roe = loc.roe || "No ROE listed";
        let roeRow = byRoe.get(roe);
        if (!roeRow) {
          roeRow = { people: new Set(), offices: new Set() };
          byRoe.set(roe, roeRow);
        }
        roeRow.people.add(person.id);
        roeRow.offices.add(office.id);
      }
    }
  }
  return { people, byCounty, byRoe, officeIds };
}

function yearComparison(roles) {
  const onlyPrior = [];
  const onlyCurrent = [];
  const same = [];
  const different = [];
  if (!directory) {
    return { onlyPrior, onlyCurrent, same, different };
  }
  for (const person of directory.people) {
    if (!personMatchesRoles(person, roles)) {
      continue;
    }
    const prior = locationsForYear(person, "2023-2024");
    const current = locationsForYear(person, "2024-2025");
    const priorIds = new Set(prior.map((loc) => loc.office_id));
    const currentIds = new Set(current.map((loc) => loc.office_id));
    if (priorIds.size === 0 && currentIds.size === 0) {
      continue;
    }
    if (priorIds.size > 0 && currentIds.size === 0) {
      onlyPrior.push(person);
      continue;
    }
    if (currentIds.size > 0 && priorIds.size === 0) {
      onlyCurrent.push(person);
      continue;
    }
    const shared = [...priorIds].some((id) => currentIds.has(id));
    if (shared) {
      same.push(person);
    } else {
      different.push({
        person,
        prior: prior.map((loc) => loc.label).join("; "),
        current: current.map((loc) => loc.label).join("; "),
      });
    }
  }
  return { onlyPrior, onlyCurrent, same, different };
}

function filteredUnplaced(years, roles) {
  if (!unplaced) {
    return [];
  }
  const yearSet = new Set(years);
  const tviOnly = roles.length === 1 && roles[0] === "TVI";
  return unplaced.people.filter((row) => {
    if (!yearSet.has(row.year) || !personMatchesRoles(row, roles)) {
      return false;
    }
    if (tviOnly && row.tvi === false) {
      return false;
    }
    return true;
  });
}

function renderStats(data, years, roles, unplacedRows) {
  const countiesWithOffice = (counties?.features || []).filter((feature) => {
    const row = data.byCounty.get(countyKey(feature.properties.name));
    return Boolean(row && row.people.size);
  }).length;
  stats.replaceChildren(
    statCard("Placed people", data.people.size),
    statCard("Offices", data.officeIds.size),
    statCard("Left off the map", new Set(unplacedRows.map((row) => row.id)).size),
    statCard("Counties with an office", countiesWithOffice),
    statCard("Counties with no office", (counties?.features.length || 0) - countiesWithOffice),
  );
  const yearLabel = years.length === 2 ? "both school years" : years[0].replace("-", "–");
  const roleLabel = roles.map((role) => ROLE_LABELS[role] || role).join(", ") || "no credential";
  announce(
    `${data.people.size} placed people and ${unplacedRows.length} rows left off the map for ${yearLabel}, ${roleLabel}.`,
  );
}

function renderMap(data) {
  if (!counties) {
    return;
  }
  const contrast = root.dataset.theme === "contrast";
  const bounds = featureBounds(counties.features);
  const max = Math.max(0, ...counties.features.map((feature) => {
    const row = data.byCounty.get(countyKey(feature.properties.name));
    return row ? row.people.size : 0;
  }));
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-labelledby", "map-heading map-legend");
  svg.setAttribute("fill-rule", "evenodd");
  for (const feature of counties.features) {
    const name = feature.properties.name;
    const key = countyKey(name);
    const row = data.byCounty.get(key);
    const count = row ? row.people.size : 0;
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", geometryPath(feature.geometry, bounds, MAP_WIDTH, MAP_HEIGHT));
    path.setAttribute("fill", countColor(count, max, contrast));
    path.setAttribute("tabindex", "0");
    path.setAttribute("role", "button");
    path.setAttribute("aria-label", `${name} County, ${count} ${count === 1 ? "person" : "people"}`);
    path.dataset.county = key;
    if (key === selectedCounty) {
      path.setAttribute("aria-current", "true");
    }
    path.addEventListener("click", () => {
      selectedCounty = key;
      render();
    });
    path.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        selectedCounty = key;
        render();
      }
    });
    svg.append(path);
  }
  mapWrap.replaceChildren(svg);
  mapLegend.textContent =
    max === 0
      ? "No placed offices match the current filters."
      : `Darker counties have more people with a public office in that county. The highest county has ${max}.`;
}

function renderCountyDetail(data) {
  if (!selectedCounty) {
    countyDetail.replaceChildren();
    const hint = document.createElement("p");
    hint.textContent = "Select a county on the map to list its offices and people.";
    countyDetail.append(hint);
    return;
  }
  const feature = counties?.features.find((item) => countyKey(item.properties.name) === selectedCounty);
  const label = feature ? `${feature.properties.name} County` : selectedCounty;
  const row = data.byCounty.get(selectedCounty);
  countyDetail.replaceChildren();
  const heading = document.createElement("h3");
  heading.textContent = label;
  countyDetail.append(heading);
  if (!row || row.people.size === 0) {
    const empty = document.createElement("p");
    empty.textContent = "No placed office in this county for the current filters.";
    countyDetail.append(empty);
    return;
  }
  const list = document.createElement("ul");
  const names = [...row.people]
    .map((id) => data.people.get(id)?.person)
    .filter(Boolean)
    .sort((left, right) => left.name.localeCompare(right.name));
  for (const person of names) {
    const item = document.createElement("li");
    const officesForPerson = [...data.people.get(person.id).offices.values()]
      .filter((entry) => countyKey(entry.office.county) === selectedCounty)
      .map((entry) => entry.loc.label);
    item.textContent = `${person.name}: ${officesForPerson.join("; ")}`;
    list.append(item);
  }
  countyDetail.append(list);
}

function renderCountyTable(data) {
  const rows = (counties?.features || []).map((feature) => {
    const key = countyKey(feature.properties.name);
    const row = data.byCounty.get(key);
    return [feature.properties.name, row ? row.people.size : 0, row ? row.offices.size : 0];
  });
  rows.sort((left, right) => right[1] - left[1] || String(left[0]).localeCompare(String(right[0])));
  fillTable(countyRows, rows);
}

function renderRoeTable(data) {
  const labels = new Set(data.byRoe.keys());
  for (const region of roes?.regions || []) {
    if (region.label) {
      labels.add(region.label);
    }
  }
  const rows = [...labels].map((label) => {
    const row = data.byRoe.get(label);
    return [label, row ? row.people.size : 0, row ? row.offices.size : 0];
  });
  rows.sort((left, right) => right[1] - left[1] || String(left[0]).localeCompare(String(right[0])));
  fillTable(roeRows, rows);
}

function renderComparison(roles) {
  const result = yearComparison(roles);
  compareStats.replaceChildren(
    statCard("Only 2023–2024", result.onlyPrior.length),
    statCard("Only 2024–2025", result.onlyCurrent.length),
    statCard("Both years, same office", result.same.length),
    statCard("Both years, different office", result.different.length),
  );
  fillTable(
    compareRows,
    result.different
      .sort((left, right) => left.person.name.localeCompare(right.person.name))
      .map((row) => [row.person.name, row.prior, row.current]),
  );
}

function renderUnplaced(rows) {
  unplacedGroups.replaceChildren();
  /** @type {Map<string, string[]>} */
  const groups = new Map();
  for (const row of rows) {
    const names = groups.get(row.reason) || [];
    if (!names.includes(row.name)) {
      names.push(row.name);
    }
    groups.set(row.reason, names);
  }
  const reasons = [...groups.keys()].sort((left, right) => {
    const size = (groups.get(right)?.length || 0) - (groups.get(left)?.length || 0);
    return size || left.localeCompare(right);
  });
  if (reasons.length === 0) {
    const empty = document.createElement("p");
    empty.textContent = "No people are left off the map for these filters.";
    unplacedGroups.append(empty);
    return;
  }
  for (const reason of reasons) {
    const names = (groups.get(reason) || []).sort((left, right) => left.localeCompare(right));
    const heading = document.createElement("h3");
    heading.textContent = `${reason} (${names.length})`;
    const list = document.createElement("ul");
    for (const name of names) {
      const item = document.createElement("li");
      item.textContent = name;
      list.append(item);
    }
    unplacedGroups.append(heading, list);
  }
}

function render() {
  if (!directory || !offices || !counties) {
    return;
  }
  const years = selectedYears();
  const roles = selectedRoles();
  const data = coverage(years, roles);
  const unplacedRows = filteredUnplaced(years, roles);
  renderStats(data, years, roles, unplacedRows);
  renderMap(data);
  renderCountyDetail(data);
  renderCountyTable(data);
  renderRoeTable(data);
  renderComparison(roles);
  renderUnplaced(unplacedRows);
}

filters.addEventListener("submit", (event) => {
  event.preventDefault();
  const url = new URL(window.location.href);
  const years = selectedYears();
  const roles = selectedRoles();
  if (years.length === 2) {
    url.searchParams.set("year", "both");
  } else if (years[0] === DEFAULT_YEAR) {
    url.searchParams.delete("year");
  } else {
    url.searchParams.set("year", years[0]);
  }
  if (roles.length === 1 && roles[0] === "TVI") {
    url.searchParams.delete("roles");
  } else {
    url.searchParams.set("roles", roles.join(","));
  }
  window.history.replaceState(null, "", url);
  render();
});

/**
 * @param {string[]} roles
 * @param {{lat: number, lng: number}} origin
 * @param {string[]} years
 */
function distanceSummary(roles, origin, years) {
  if (!directory || !offices) {
    return { nearest: null, within25: 0, within50: 0 };
  }
  const within25 = new Set();
  const within50 = new Set();
  /** @type {{person: object, loc: object, miles: number, phone: string} | null} */
  let nearest = null;
  for (const year of years) {
    const ranked = nearestPeople(directory.people, offices, origin, {
      year,
      roles,
      limit: Number.POSITIVE_INFINITY,
    });
    for (const row of ranked) {
      if (!nearest || row.miles < nearest.miles) {
        nearest = row;
      }
      if (row.miles <= 25) {
        within25.add(row.person.id);
      }
      if (row.miles <= 50) {
        within50.add(row.person.id);
      }
    }
  }
  return { nearest, within25: within25.size, within50: within50.size };
}

placeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!directory || !offices || !places) {
    return;
  }
  const query = placeInput.value.trim();
  placeSummary.replaceChildren();
  if (!query) {
    const empty = document.createElement("p");
    empty.textContent = "Enter an Illinois city, ZIP code, or street address.";
    placeSummary.append(empty);
    return;
  }
  const origin = await locateQuery(query, places);
  if (origin.status === "ambiguous") {
    const message = document.createElement("p");
    message.textContent = `${[...new Set(origin.names)].join(" and ")} matches more than one Illinois place. Enter a ZIP code.`;
    placeSummary.append(message);
    return;
  }
  if (origin.status !== "ok") {
    const message = document.createElement("p");
    message.textContent = "No Illinois city or ZIP code matched.";
    placeSummary.append(message);
    return;
  }
  const heading = document.createElement("p");
  const prefix = origin.how === "fallback" ? "The street lookup did not return an Illinois point. " : "";
  heading.textContent = `${prefix}Coverage from ${origin.label}.`;
  placeSummary.append(heading);
  const table = document.createElement("table");
  const caption = document.createElement("caption");
  caption.textContent = "Nearest office and counts within 25 and 50 miles";
  table.append(caption);
  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const label of ["Credential", "Nearest miles", "Within 25 miles", "Within 50 miles"]) {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = label;
    headRow.append(th);
  }
  thead.append(headRow);
  table.append(thead);
  const tbody = document.createElement("tbody");
  const years = selectedYears();
  const roles = selectedRoles();
  const lines = roles.map((role) => [role]);
  if (roles.length > 1) {
    lines.unshift(roles);
  }
  for (const set of lines) {
    const summary = distanceSummary(set, origin, years);
    const label = set.length === 1 ? ROLE_LABELS[set[0]] || set[0] : "Selected credentials";
    const tr = document.createElement("tr");
    const credential = document.createElement("th");
    credential.scope = "row";
    credential.textContent = label;
    const miles = document.createElement("td");
    miles.textContent = summary.nearest ? summary.nearest.miles.toFixed(1) : "None";
    const cell25 = document.createElement("td");
    cell25.textContent = String(summary.within25);
    const cell50 = document.createElement("td");
    cell50.textContent = String(summary.within50);
    tr.append(credential, miles, cell25, cell50);
    tbody.append(tr);
  }
  table.append(tbody);
  placeSummary.append(table);
});

function applyParams() {
  const params = new URLSearchParams(window.location.search);
  const year = params.get("year");
  for (const input of yearInputs) {
    input.checked = year ? input.value === year : input.value === DEFAULT_YEAR;
  }
  const rolesParam = params.get("roles");
  const roles = rolesParam
    ? rolesParam
        .split(",")
        .map((role) => role.trim())
        .filter((role) => ROLE_ORDER.includes(role))
    : ["TVI"];
  const wanted = new Set(roles.length ? roles : ["TVI"]);
  for (const input of roleInputs) {
    input.checked = wanted.has(input.value);
  }
}

Promise.all([
  loadJson("data/tvis.json"),
  loadJson("data/entities.json"),
  loadJson("data/il_locations.json"),
  loadJson("data/unplaced.json"),
  loadJson("data/il_counties.json"),
  loadJson("data/illinois_roes.json"),
])
  .then(([tvis, entities, locationFile, unplacedFile, countyFile, roeFile]) => {
    directory = tvis;
    offices = indexOffices(entities);
    places = locationFile;
    unplaced = unplacedFile;
    counties = countyFile;
    roes = roeFile;
    applyParams();
    render();
  })
  .catch(() => {
    announce("The coverage files did not load. Check the connection and reload the page.");
  });

