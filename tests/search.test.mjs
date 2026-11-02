import assert from "node:assert/strict";
import test from "node:test";

import {
  fallbackInText,
  haversineMiles,
  nearestPeople,
  normalizePlace,
  resolveLocalQuery,
  resolveOffline,
  indexOffices,
} from "../search.js";

const places = {
  places: [
    { name: "Springfield", key: "springfield", lat: 39.78, lng: -89.65 },
    { name: "Wilmington", key: "wilmington", lat: 41.3, lng: -88.15 },
    { name: "Wilmington", key: "wilmington", lat: 39.44, lng: -88.99 },
    { name: "Chicago", key: "chicago", lat: 41.88, lng: -87.63 },
    { name: "Saint Charles", key: "saint charles", lat: 41.91, lng: -88.31 },
  ],
  zips: {
    "62704": { lat: 39.76, lng: -89.67 },
  },
};

test("place names match the gazetteer keys", () => {
  assert.equal(normalizePlace("St. Charles"), "saint charles");
  assert.equal(normalizePlace("DeKalb"), "dekalb");
  assert.equal(normalizePlace("La Salle"), "lasalle");
  assert.equal(normalizePlace("McHenry"), "mchenry");
  assert.equal(normalizePlace("Springfield, Illinois"), "springfield");
  assert.equal(normalizePlace("Adair CDP"), "adair");
});

test("one degree of latitude is about 69 miles", () => {
  const distance = haversineMiles(40, -89, 41, -89);
  assert.ok(distance > 68.5 && distance < 69.5);
  assert.equal(haversineMiles(40, -89, 40, -89), 0);
});

test("a ZIP, a city, and an ambiguous city resolve locally", () => {
  const zip = resolveLocalQuery("62704", places);
  assert.equal(zip.status, "ok");
  assert.equal(zip.label, "62704");
  const city = resolveLocalQuery("Springfield, IL", places);
  assert.equal(city.status, "ok");
  assert.equal(city.label, "Springfield");
  const ambiguous = resolveLocalQuery("Wilmington", places);
  assert.equal(ambiguous.status, "ambiguous");
  assert.equal(resolveLocalQuery("Nowhere", places).status, "missing");
});

test("a city plus ZIP resolves from the ZIP when it is not a street", () => {
  const found = resolveOffline("Springfield, IL 62704", places);
  assert.equal(found.status, "ok");
  assert.equal(found.label, "62704");
  assert.equal(found.how, "zip");
  assert.equal(resolveOffline("100 W Randolph St, Chicago, IL 60601", places).status, "street");
  assert.equal(resolveOffline("Nowhere special", places).status, "missing");
});

test("a street that fails still finds the ZIP or city inside it", () => {
  const byZip = fallbackInText("123 Main St, Springfield, IL 62704", places);
  assert.equal(byZip.label, "62704");
  const byCity = fallbackInText("100 W Randolph St, Chicago, IL", places);
  assert.equal(byCity.label, "Chicago");
});

test("search keeps the closer office and honors the limits", () => {
  const people = [
    {
      name: "Ada Lovelace",
      om: "Yes",
      ei: "Not listed",
      locations: [
        { office_id: "far", phone_office_id: "far", label: "Far office" },
        { office_id: "near", phone_office_id: "near", label: "Near office" },
      ],
    },
    {
      name: "Grace Hopper",
      om: "Not listed",
      ei: "Yes",
      locations: [{ office_id: "near", phone_office_id: "missing", label: "Grace office" }],
    },
  ];
  const offices = indexOffices({
    offices: [
      { id: "far", lat: 42, lng: -87, phone: "Not listed" },
      { id: "near", lat: 40.1, lng: -89, phone: "217-555-0100" },
    ],
  });
  const ranked = nearestPeople(people, offices, { lat: 40, lng: -89 }, {});
  assert.equal(ranked[0].person.name, "Ada Lovelace");
  assert.equal(ranked[0].loc.label, "Near office");
  assert.equal(ranked[0].phone, "217-555-0100");
  assert.equal(ranked[1].phone, "Not listed");
  const onlyOm = nearestPeople(people, offices, { lat: 40, lng: -89 }, { om: true });
  assert.deepEqual(
    onlyOm.map((row) => row.person.name),
    ["Ada Lovelace"],
  );
});

test("year and credential filters keep the matching offices", () => {
  const people = [
    {
      name: "Ada Lovelace",
      roles: ["TVI", "COMS"],
      om: "Yes",
      ei: "Not listed",
      years: {
        "2024-2025": [{ office_id: "near", phone_office_id: "near", label: "Ada 2025" }],
        "2023-2024": [{ office_id: "far", phone_office_id: "far", label: "Ada 2024" }],
      },
    },
    {
      name: "Ana Leffel",
      roles: ["CLVT"],
      om: "Not listed",
      ei: "Not listed",
      years: {
        "2024-2025": [{ office_id: "near", phone_office_id: "near", label: "Ana office" }],
        "2023-2024": [],
      },
    },
  ];
  const offices = indexOffices({
    offices: [
      { id: "far", lat: 42, lng: -87, phone: "Not listed" },
      { id: "near", lat: 40.1, lng: -89, phone: "217-555-0100" },
    ],
  });
  const tviCurrent = nearestPeople(people, offices, { lat: 40, lng: -89 }, {
    year: "2024-2025",
    roles: ["TVI"],
  });
  assert.deepEqual(
    tviCurrent.map((row) => row.person.name),
    ["Ada Lovelace"],
  );
  assert.equal(tviCurrent[0].loc.label, "Ada 2025");
  const prior = nearestPeople(people, offices, { lat: 40, lng: -89 }, {
    year: "2023-2024",
    roles: ["TVI"],
  });
  assert.equal(prior[0].loc.label, "Ada 2024");
  const clvt = nearestPeople(people, offices, { lat: 40, lng: -89 }, {
    year: "2024-2025",
    roles: ["CLVT"],
  });
  assert.deepEqual(
    clvt.map((row) => row.person.name),
    ["Ana Leffel"],
  );
});
