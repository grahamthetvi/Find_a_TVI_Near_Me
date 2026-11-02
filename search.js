/** Distance search for the static directory. No network calls live here. */

const EARTH_RADIUS_MILES = 3958.7613;

/**
 * @param {string} value
 * @returns {string}
 */
export function normalizePlace(value) {
  let text = String(value || "")
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/\./g, " ");
  text = text.replace(/\([^)]*\)/g, " ");
  text = text.replace(/[^a-z0-9]+/g, " ").replace(/\s+/g, " ").trim();
  text = text
    .replace(/du page/g, "dupage")
    .replace(/de kalb/g, "dekalb")
    .replace(/de witt/g, "dewitt")
    .replace(/la salle/g, "lasalle")
    .replace(/la grange/g, "lagrange")
    .replace(/saint clair/g, "st clair");
  text = text.replace(/\bmc\s+/g, "mc");
  text = text.replace(/\s+(city|village|town|cdp|borough)$/g, "");
  text = text.replace(/\bst\b/g, "saint");
  text = text.replace(/\bmt\b/g, "mount");
  text = text.replace(/\s+(illinois|il)$/g, "");
  return text.trim();
}

/**
 * @param {number} lat1
 * @param {number} lng1
 * @param {number} lat2
 * @param {number} lng2
 * @returns {number}
 */
export function haversineMiles(lat1, lng1, lat2, lng2) {
  const phi1 = (lat1 * Math.PI) / 180;
  const phi2 = (lat2 * Math.PI) / 180;
  const deltaPhi = ((lat2 - lat1) * Math.PI) / 180;
  const deltaLambda = ((lng2 - lng1) * Math.PI) / 180;
  const half =
    Math.sin(deltaPhi / 2) ** 2 +
    Math.cos(phi1) * Math.cos(phi2) * Math.sin(deltaLambda / 2) ** 2;
  return 2 * EARTH_RADIUS_MILES * Math.asin(Math.min(1, Math.sqrt(half)));
}

/**
 * @param {string} query
 * @returns {boolean}
 */
export function hasHouseNumber(query) {
  return /^\s*\d+\s+\S/.test(query);
}

/**
 * @param {{offices: Array<{id: string}>}} entities
 * @returns {Map<string, object>}
 */
export function indexOffices(entities) {
  return new Map(entities.offices.map((office) => [office.id, office]));
}

/**
 * @param {string} query
 * @param {{places: Array<{name: string, key: string, lat: number, lng: number}>, zips: Record<string, {lat: number, lng: number}>}} places
 */
export function resolveLocalQuery(query, places) {
  const trimmed = query.trim();
  const zipOnly = trimmed.match(/^(\d{5})(?:-\d{4})?$/);
  if (zipOnly) {
    const point = places.zips[zipOnly[1]];
    if (!point) {
      return { status: "missing" };
    }
    return { status: "ok", lat: point.lat, lng: point.lng, label: zipOnly[1], how: "zip" };
  }
  const key = normalizePlace(trimmed);
  const matches = places.places.filter((place) => place.key === key);
  if (matches.length === 1) {
    return {
      status: "ok",
      lat: matches[0].lat,
      lng: matches[0].lng,
      label: matches[0].name,
      how: "city",
    };
  }
  if (matches.length > 1) {
    return {
      status: "ambiguous",
      names: [...new Set(matches.map((place) => place.name))],
    };
  }
  return { status: "missing" };
}

/**
 * Resolve a query from the local gazetteer.
 * A house-numbered street is left as `street` so the page can try the Census
 * geocoder. Any other miss uses a ZIP or city written inside the text.
 *
 * @param {string} query
 * @param {{places: Array<{name: string, key: string, lat: number, lng: number}>, zips: Record<string, {lat: number, lng: number}>}} places
 */
export function resolveOffline(query, places) {
  const local = resolveLocalQuery(query, places);
  if (local.status !== "missing") {
    return local;
  }
  if (hasHouseNumber(query)) {
    return { status: "street" };
  }
  return fallbackInText(query, places);
}

/**
 * @param {string} query
 * @param {{places: Array<{name: string, key: string, lat: number, lng: number}>, zips: Record<string, {lat: number, lng: number}>}} places
 */
export function fallbackInText(query, places) {
  const zipMatch = query.match(/\b(\d{5})(?:-\d{4})?\b/);
  if (zipMatch && places.zips[zipMatch[1]]) {
    const point = places.zips[zipMatch[1]];
    return { status: "ok", lat: point.lat, lng: point.lng, label: zipMatch[1], how: "zip" };
  }
  const normalized = ` ${normalizePlace(query)} `;
  /** @type {Array<{name: string, key: string, lat: number, lng: number}>} */
  const hits = [];
  for (const place of places.places) {
    if (place.key && normalized.includes(` ${place.key} `)) {
      hits.push(place);
    }
  }
  if (hits.length === 0) {
    return { status: "missing" };
  }
  const longest = Math.max(...hits.map((place) => place.key.length));
  const best = hits.filter((place) => place.key.length === longest);
  const coordinates = new Set(best.map((place) => `${place.lat},${place.lng}`));
  if (coordinates.size > 1) {
    return { status: "ambiguous", names: [...new Set(best.map((place) => place.name))] };
  }
  return {
    status: "ok",
    lat: best[0].lat,
    lng: best[0].lng,
    label: best[0].name,
    how: "city",
  };
}

export const DEFAULT_YEAR = "2024-2025";
export const SCHOOL_YEARS = ["2023-2024", "2024-2025"];
export const ROLE_ORDER = ["TVI", "COMS", "CATIS", "CLVT", "CVRT"];
export const ROLE_LABELS = {
  TVI: "Teacher of the Visually Impaired (TVI)",
  COMS: "Orientation and mobility (COMS)",
  CATIS: "Certified Assistive Technology Instructional Specialist (CATIS)",
  CLVT: "Certified Low Vision Therapist (CLVT)",
  CVRT: "Certified Vision Rehabilitation Therapist (CVRT)",
};

/**
 * @param {string} value
 * @returns {string}
 */
export function countyKey(value) {
  return normalizePlace(String(value || "").replace(/\s+count(?:y|ies)$/i, ""));
}

/**
 * @param {object} person
 * @param {string} year
 * @returns {Array<{office_id: string, phone_office_id: string, label: string, roe?: string}>}
 */
export function locationsForYear(person, year) {
  if (person.years && Array.isArray(person.years[year])) {
    return person.years[year];
  }
  if (year === DEFAULT_YEAR && Array.isArray(person.locations)) {
    return person.locations;
  }
  return [];
}

/**
 * @param {object} person
 * @param {string[] | undefined} roles
 * @returns {boolean}
 */
export function personMatchesRoles(person, roles) {
  if (!roles) {
    return true;
  }
  if (roles.length === 0) {
    return false;
  }
  const have = Array.isArray(person.roles) ? person.roles : ["TVI"];
  return roles.some((role) => have.includes(role));
}

/**
 * @param {string[]} roles
 * @returns {string}
 */
export function roleList(roles) {
  const have = Array.isArray(roles) ? roles : [];
  return have.join(", ") || "Not listed";
}

/**
 * @param {Array<object>} people
 * @param {Map<string, {lat?: number, lng?: number, phone?: string}>} offices
 * @param {{lat: number, lng: number}} origin
 * @param {{om?: boolean, ei?: boolean, limit?: number, year?: string, roles?: string[]}} options
 */
export function nearestPeople(people, offices, origin, options) {
  const limit = options.limit ?? 10;
  const year = options.year ?? DEFAULT_YEAR;
  /** @type {Array<{person: object, loc: object, miles: number, phone: string}>} */
  const ranked = [];
  for (const person of people) {
    if (!personMatchesRoles(person, options.roles)) {
      continue;
    }
    if (options.om && person.om !== "Yes") {
      continue;
    }
    if (options.ei && person.ei !== "Yes") {
      continue;
    }
    /** @type {{person: object, loc: object, miles: number, phone: string} | null} */
    let best = null;
    for (const loc of locationsForYear(person, year)) {
      const office = offices.get(loc.office_id);
      if (!office || typeof office.lat !== "number" || typeof office.lng !== "number") {
        continue;
      }
      const miles = haversineMiles(origin.lat, origin.lng, office.lat, office.lng);
      const phoneOffice = offices.get(loc.phone_office_id);
      const phone = phoneOffice && phoneOffice.phone ? phoneOffice.phone : "Not listed";
      if (!best || miles < best.miles || (miles === best.miles && loc.label < best.loc.label)) {
        best = { person, loc, miles, phone };
      }
    }
    if (best) {
      ranked.push(best);
    }
  }
  ranked.sort(
    (left, right) =>
      left.miles - right.miles || left.person.name.localeCompare(right.person.name),
  );
  return ranked.slice(0, limit);
}

/**
 * @param {string} query
 * @param {{places: Array<{name: string, key: string, lat: number, lng: number}>, zips: Record<string, {lat: number, lng: number}>}} places
 */
export async function locateQuery(query, places) {
  const local = resolveOffline(query, places);
  if (local.status !== "street") {
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
