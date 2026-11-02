import {
  DEFAULT_YEAR,
  ROLE_ORDER,
  indexOffices,
  locateQuery,
  nearestPeople,
  roleList,
} from "./search.js";

const form = document.querySelector("#search-form");
const queryInput = document.querySelector("#q");
const yearInputs = [...document.querySelectorAll('input[name="year"]')];
const roleInputs = ROLE_ORDER.map((role) =>
  document.querySelector(`input[name="roles"][value="${role}"]`),
).filter(Boolean);
const eiInput = document.querySelector("#only-ei");
const searchButton = document.querySelector("#search-button");
const themeButton = document.querySelector("#theme");
const status = document.querySelector("#status");
const omitted = document.querySelector("#omitted");
const caption = document.querySelector("#results-caption");
const rows = document.querySelector("#result-rows");
const root = document.documentElement;

/** @type {{people: Array<object>, omitted_people?: number, omitted_note?: string, years?: Record<string, {omitted_note?: string}>} | null} */
let directory = null;
/** @type {Map<string, object> | null} */
let offices = null;
/** @type {{places: Array<object>, zips: Record<string, {lat: number, lng: number}>} | null} */
let places = null;

const THEME_KEY = "tvi-theme";

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

function clearRows() {
  rows.replaceChildren();
}

/**
 * @param {string} value
 * @returns {Node}
 */
function textCell(value) {
  return document.createTextNode(value || "Not listed");
}

/**
 * @param {string} phone
 * @returns {Node}
 */
function phoneNode(phone) {
  if (!phone || phone === "Not listed") {
    return document.createTextNode("Not listed");
  }
  const digits = phone.replace(/[^\d+]/g, "");
  if (digits.length < 7) {
    return document.createTextNode(phone);
  }
  const link = document.createElement("a");
  link.href = `tel:${digits}`;
  link.textContent = phone;
  return link;
}

/**
 * @param {string} linkedin
 * @param {string} name
 * @returns {Node}
 */
function profileNode(linkedin, name) {
  if (!linkedin || linkedin === "Not listed") {
    return document.createTextNode("Not listed");
  }
  if (!/^https?:\/\//i.test(linkedin)) {
    return document.createTextNode(linkedin);
  }
  const link = document.createElement("a");
  link.href = linkedin;
  link.rel = "noopener noreferrer";
  link.textContent = `Profile for ${name}`;
  return link;
}

/**
 * @param {string} message
 */
function announce(message) {
  status.textContent = message;
  status.focus();
}

function selectedYear() {
  const checked = yearInputs.find((input) => input.checked);
  return checked ? checked.value : DEFAULT_YEAR;
}

function selectedRoles() {
  return roleInputs.filter((input) => input.checked).map((input) => input.value);
}

function setYear(year) {
  for (const input of yearInputs) {
    input.checked = input.value === year;
  }
}

function setRoles(roles) {
  const wanted = new Set(roles);
  for (const input of roleInputs) {
    input.checked = wanted.has(input.value);
  }
}

function omittedNote(year) {
  if (!directory) {
    return "";
  }
  const yearNote = directory.years?.[year]?.omitted_note;
  if (typeof yearNote === "string" && yearNote) {
    return yearNote;
  }
  return directory.omitted_note || "";
}

/**
 * @param {Array<{person: {name: string, om: string, ei: string, linkedin: string, roles?: string[]}, loc: {label: string}, miles: number, phone: string}>} ranked
 * @param {string} placeLabel
 * @param {string} year
 * @param {boolean} ei
 * @param {string} prefix
 */
function renderResults(ranked, placeLabel, year, ei, prefix) {
  clearRows();
  const yearLabel = year.replace("-", "–");
  const eiNote = ei ? " listed for Early Intervention" : "";
  if (ranked.length === 0) {
    caption.textContent = `No people near ${placeLabel} for ${yearLabel}`;
    announce(`${prefix}No people near ${placeLabel} for ${yearLabel}${eiNote}.`.replace("  ", " "));
    return;
  }
  caption.textContent = `${ranked.length} ${ranked.length === 1 ? "person" : "people"} near ${placeLabel} for ${yearLabel}`;
  for (const row of ranked) {
    const tr = document.createElement("tr");
    const employer = document.createElement("th");
    employer.scope = "row";
    employer.textContent = row.loc.label;
    tr.append(
      employer,
      cell(row.miles.toFixed(1)),
      cellNode(profileNode(row.person.linkedin, row.person.name)),
      cellNode(phoneNode(row.phone)),
      cell(row.person.name),
      cell(roleList(row.person.roles)),
      cell(row.person.om),
      cell(row.person.ei),
    );
    rows.append(tr);
  }
  const closest = ranked[0].miles.toFixed(1);
  announce(
    `${prefix}${ranked.length} ${ranked.length === 1 ? "person" : "people"} near ${placeLabel} for ${yearLabel}${eiNote}. The closest office is ${closest} miles away.`,
  );
}

/**
 * @param {string} value
 */
function cell(value) {
  const td = document.createElement("td");
  td.append(textCell(value));
  return td;
}

/**
 * @param {Node} node
 */
function cellNode(node) {
  const td = document.createElement("td");
  td.append(node);
  return td;
}

/**
 * @param {string} query
 * @param {string} year
 * @param {string[]} roles
 * @param {boolean} ei
 */
async function search(query, year, roles, ei) {
  if (!directory || !offices || !places) {
    announce("The directory is still loading.");
    return;
  }
  omitted.textContent = omittedNote(year);
  const origin = await locateQuery(query, places);
  if (origin.status === "ambiguous") {
    clearRows();
    caption.textContent = "More than one Illinois place matches";
    const names = [...new Set(origin.names)].join(" and ");
    announce(`${names} matches more than one Illinois place. Enter a ZIP code.`);
    return;
  }
  if (origin.status !== "ok") {
    clearRows();
    caption.textContent = "No Illinois place matched";
    announce("No Illinois city or ZIP code matched. Enter a city, a 5-digit ZIP code, or a street address in Illinois.");
    return;
  }
  const ranked = nearestPeople(directory.people, offices, origin, {
    year,
    roles,
    ei,
    limit: 10,
  });
  const prefix =
    origin.how === "fallback"
      ? `The street lookup did not return an Illinois point. `
      : "";
  renderResults(ranked, origin.label, year, ei, prefix);
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = queryInput.value.trim();
  if (!query) {
    announce("Enter an Illinois city, ZIP code, or street address.");
    return;
  }
  const year = selectedYear();
  const roles = selectedRoles();
  const url = new URL(window.location.href);
  url.searchParams.set("q", query);
  if (year === DEFAULT_YEAR) {
    url.searchParams.delete("year");
  } else {
    url.searchParams.set("year", year);
  }
  if (roles.length === 1 && roles[0] === "TVI") {
    url.searchParams.delete("roles");
  } else {
    url.searchParams.set("roles", roles.join(","));
  }
  if (roles.length === 1 && roles[0] === "COMS") {
    url.searchParams.set("om", "1");
  } else {
    url.searchParams.delete("om");
  }
  if (eiInput.checked) {
    url.searchParams.set("ei", "1");
  } else {
    url.searchParams.delete("ei");
  }
  window.history.replaceState(null, "", url);
  search(query, year, roles, eiInput.checked);
});

searchButton.disabled = true;
searchButton.textContent = "Loading the directory";

Promise.all([loadJson("data/tvis.json"), loadJson("data/entities.json"), loadJson("data/il_locations.json")])
  .then(([tvis, entities, locationFile]) => {
    directory = tvis;
    offices = indexOffices(entities);
    places = locationFile;
    const params = new URLSearchParams(window.location.search);
    const year = params.get("year") === "2023-2024" ? "2023-2024" : DEFAULT_YEAR;
    setYear(year);
    const rolesParam = params.get("roles");
    if (rolesParam) {
      setRoles(
        rolesParam
          .split(",")
          .map((role) => role.trim())
          .filter((role) => ROLE_ORDER.includes(role)),
      );
    } else if (params.get("om") === "1") {
      setRoles(["COMS"]);
    } else {
      setRoles(["TVI"]);
    }
    if (params.get("ei") === "1") {
      eiInput.checked = true;
    }
    omitted.textContent = omittedNote(year);
    searchButton.disabled = false;
    searchButton.textContent = "Search";
    const query = params.get("q");
    if (query) {
      queryInput.value = query;
      search(query, selectedYear(), selectedRoles(), eiInput.checked);
    }
  })
  .catch(() => {
    searchButton.textContent = "Search";
    announce("The directory did not load. Check the connection and reload the page.");
  });
