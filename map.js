/** SVG paths for Illinois county GeoJSON. */

/**
 * @param {Array<{geometry: {coordinates: object}}>} features
 */
export function featureBounds(features) {
  let minLng = Infinity;
  let minLat = Infinity;
  let maxLng = -Infinity;
  let maxLat = -Infinity;

  /**
   * @param {object} coords
   */
  function walk(coords) {
    if (typeof coords[0] === "number") {
      const lng = coords[0];
      const lat = coords[1];
      minLng = Math.min(minLng, lng);
      maxLng = Math.max(maxLng, lng);
      minLat = Math.min(minLat, lat);
      maxLat = Math.max(maxLat, lat);
      return;
    }
    for (const item of coords) {
      walk(item);
    }
  }

  for (const feature of features) {
    walk(feature.geometry.coordinates);
  }
  return { minLng, minLat, maxLng, maxLat };
}

/**
 * @param {number} lng
 * @param {number} lat
 * @param {{minLng: number, minLat: number, maxLng: number, maxLat: number}} bounds
 * @param {number} width
 * @param {number} height
 * @param {number} [pad]
 * @returns {[number, number]}
 */
export function project(lng, lat, bounds, width, height, pad = 12) {
  const meanLat = ((bounds.minLat + bounds.maxLat) / 2 * Math.PI) / 180;
  const xRatio = Math.cos(meanLat);
  const dx = (bounds.maxLng - bounds.minLng) * xRatio;
  const dy = bounds.maxLat - bounds.minLat;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  const scale = Math.min(innerW / dx, innerH / dy);
  const x = pad + (lng - bounds.minLng) * xRatio * scale + (innerW - dx * scale) / 2;
  const y = pad + (bounds.maxLat - lat) * scale + (innerH - dy * scale) / 2;
  return [x, y];
}

/**
 * @param {{type: string, coordinates: object}} geometry
 * @param {{minLng: number, minLat: number, maxLng: number, maxLat: number}} bounds
 * @param {number} width
 * @param {number} height
 */
export function geometryPath(geometry, bounds, width, height) {
  const polygons = geometry.type === "Polygon" ? [geometry.coordinates] : geometry.coordinates;
  const parts = [];
  for (const polygon of polygons) {
    for (const ring of polygon) {
      const commands = ring.map((point, index) => {
        const [x, y] = project(point[0], point[1], bounds, width, height);
        return `${index === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
      });
      parts.push(`${commands.join(" ")} Z`);
    }
  }
  return parts.join(" ");
}

/**
 * @param {number} count
 * @param {number} max
 * @param {boolean} contrast
 */
export function countColor(count, max, contrast) {
  if (count <= 0) {
    return contrast ? "#1a1400" : "#f4f6f8";
  }
  const t = max <= 0 ? 0 : Math.min(1, count / max);
  if (contrast) {
    const yellow = Math.round(90 + t * 165);
    return `rgb(${yellow}, ${Math.round(yellow * 0.84)}, 10)`;
  }
  const red = Math.round(226 - t * 175);
  const green = Math.round(234 - t * 145);
  const blue = Math.round(248 - t * 103);
  return `rgb(${red}, ${green}, ${blue})`;
}
