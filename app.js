import {
  fallbackInText,
  hasHouseNumber,
  indexOffices,
  nearestPeople,
  resolveLocalQuery,
} from "./search.js";

const form = document.querySelector("#search-form");
const queryInput = document.querySelector("#q");
const omInput = document.querySelector("#only-om");
const eiInput = document.querySelector("#only-ei");
const searchButton = document.querySelector("#search-button");
const themeButton = document.querySelector("#theme");
const status = document.querySelector("#status");
const omitted = document.querySelector("#omitted");
const caption = document.querySelector("#results-caption");
const rows = document.querySelector("#result-rows");
const root = document.documentElement;

/** @type {{people: Array<object>, omitted_people?: number} | null} */
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

/**
 * @param {Array<{person: {name: string, om: string, ei: string, linkedin: string}, loc: {label: string}, miles: number, phone: string}>} ranked
 * @param {string} placeLabel
 * @param {boolean} om
 * @param {boolean} ei
 * @param {string} prefix
 */
function renderResults(ranked, placeLabel, om, ei, prefix) {
  clearRows();
  const limitNote = limitPhrase(om, ei);
  if (ranked.length === 0) {
    caption.textContent = `No teachers near ${placeLabel}`;
    announce(`${prefix}No teachers near ${placeLabel}${limitNote}.`.replace("  ", " "));
    return;
  }
  caption.textContent = `${ranked.length} ${ranked.length === 1 ? "teacher" : "teachers"} near ${placeLabel}`;
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
      cell(row.person.om),
      cell(row.person.ei),
    );
    rows.append(tr);
  }
  const closest = ranked[0].miles.toFixed(1);
  announce(
    `${prefix}${ranked.length} ${ranked.length === 1 ? "teacher" : "teachers"} near ${placeLabel}${limitNote}. The closest office is ${closest} miles away.`,
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
 * @param {boolean} om
 * @param {boolean} ei
 */
function limitPhrase(om, ei) {
  if (om && ei) {
    return " listed for orientation and mobility and Early Intervention";
  }
  if (om) {
    return " listed for orientation and mobility";
  }
  if (ei) {
    return " listed for Early Intervention";
  }
  return "";
}

/**
 * @param {string} query
 */
async function locate(query) {
  if (!places) {
    return { status: "missing" };
  }
  const local = resolveLocalQuery(query, places);
  if (local.status !== "missing" || !hasHouseNumber(query)) {
    return local;
  }
  try {
    const url = new URL("https://geocoding.geo.census.gov/geocoder/locations/onelineaddress");
    url.searchParams.set("address", query);
    url.searchParams.set("benchmark", "Public_AR_Current");
    url.searchParams.set("format", "json");
    const response = await fetch(url);
    if (response.ok) {
      const body = await response.json();
      const matches = body?.result?.addressMatches ?? [];
      for (const match of matches) {
        if (match?.addressComponents?.state !== "IL") {
          continue;
        }
        const lat = match?.coordinates?.y;
        const lng = match?.coordinates?.x;
        if (typeof lat !== "number" || typeof lng !== "number") {
          continue;
        }
        return {
          status: "ok",
          lat,
          lng,
          label: match.matchedAddress || query,
          how: "street",
        };
      }
    }
  } catch {
    /* Fall through to the city or ZIP written in the same address. */
  }
  const fallback = fallbackInText(query, places);
  if (fallback.status === "ok") {
    return { ...fallback, how: "fallback" };
  }
  return fallback;
}

/**
 * @param {string} query
 * @param {boolean} om
 * @param {boolean} ei
 */
async function search(query, om, ei) {
  if (!directory || !offices || !places) {
    announce("The directory is still loading.");
    return;
  }
  const origin = await locate(query);
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
  const ranked = nearestPeople(directory.people, offices, origin, { om, ei, limit: 10 });
  const prefix =
    origin.how === "fallback"
      ? `The street lookup did not return an Illinois point. `
      : "";
  renderResults(ranked, origin.label, om, ei, prefix);
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = queryInput.value.trim();
  if (!query) {
    announce("Enter an Illinois city, ZIP code, or street address.");
    return;
  }
  const url = new URL(window.location.href);
  url.searchParams.set("q", query);
  if (omInput.checked) {
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
  search(query, omInput.checked, eiInput.checked);
});

searchButton.disabled = true;
searchButton.textContent = "Loading the directory";

Promise.all([loadJson("data/tvis.json"), loadJson("data/entities.json"), loadJson("data/il_locations.json")])
  .then(([tvis, entities, locationFile]) => {
    directory = tvis;
    offices = indexOffices(entities);
    places = locationFile;
    if (tvis.omitted_note) {
      omitted.textContent = tvis.omitted_note;
    }
    searchButton.disabled = false;
    searchButton.textContent = "Search";
    const params = new URLSearchParams(window.location.search);
    const query = params.get("q");
    if (params.get("om") === "1") {
      omInput.checked = true;
    }
    if (params.get("ei") === "1") {
      eiInput.checked = true;
    }
    if (query) {
      queryInput.value = query;
      search(query, omInput.checked, eiInput.checked);
    }
  })
  .catch(() => {
    searchButton.textContent = "Search";
    announce("The directory did not load. Check the connection and reload the page.");
  });
