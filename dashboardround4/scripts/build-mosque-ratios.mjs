#!/usr/bin/env node
// Computes real, coordinate-derived residential:mosque ratios per region and
// per local-authority district, from the full (non-public) research CSV.
//
// Why coordinates and not the CSV's own `region`/`nation` columns: those are
// blank for every mosque row (and every residential row) in this dataset —
// there is no region/nation breakdown to read. Latitude/longitude ARE
// populated for all 22,543 residential and all 32 mosque records, so region
// and district are derived by point-in-polygon matching against the same
// boundary files build-geo.mjs already produces, rather than fabricated.
//
// Usage: node scripts/build-mosque-ratios.mjs

import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.join(__dirname, '../src/lib/data');
const CSV_PATH = path.join(__dirname, '../../data/output/uk_church_conversions_20260615.csv');

function log(msg) {
	console.log(`[build-mosque-ratios] ${msg}`);
}

function parseCsv(text) {
	const lines = text.split('\n');
	const header = lines[0].split(',');
	const idx = Object.fromEntries(header.map((h, i) => [h, i]));
	const rows = [];
	for (let i = 1; i < lines.length; i++) {
		const line = lines[i];
		if (!line.trim()) continue;
		// fields used here (conversion_type, latitude, longitude) never
		// contain commas/quotes in this dataset, so a plain split is safe.
		const cols = line.split(',');
		rows.push({
			conversion_type: cols[idx.conversion_type],
			latitude: parseFloat(cols[idx.latitude]),
			longitude: parseFloat(cols[idx.longitude])
		});
	}
	return rows;
}

function pointInRing(lon, lat, ring) {
	let inside = false;
	for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
		const [xi, yi] = ring[i];
		const [xj, yj] = ring[j];
		const intersects = yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi;
		if (intersects) inside = !inside;
	}
	return inside;
}

function pointInFeature(lon, lat, geometry) {
	const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
	for (const rings of polygons) {
		if (!pointInRing(lon, lat, rings[0])) continue;
		const inHole = rings.slice(1).some((hole) => pointInRing(lon, lat, hole));
		if (!inHole) return true;
	}
	return false;
}

function matchFeature(lon, lat, fc, propKey) {
	for (const f of fc.features) {
		if (pointInFeature(lon, lat, f.geometry)) return f.properties[propKey];
	}
	return null;
}

function main() {
	log(`reading ${path.relative(process.cwd(), CSV_PATH)}`);
	const rows = parseCsv(readFileSync(CSV_PATH, 'utf8'));
	const relevant = rows.filter(
		(r) => (r.conversion_type === 'residential' || r.conversion_type === 'mosque') && !isNaN(r.latitude) && !isNaN(r.longitude)
	);
	log(`${relevant.length} geocoded residential/mosque rows`);

	const regionsGeo = JSON.parse(readFileSync(path.join(DATA_DIR, 'regions.json'), 'utf8'));
	const districtsGeo = JSON.parse(readFileSync(path.join(DATA_DIR, 'districts.json'), 'utf8'));

	const regions = {};
	const districts = {};
	let nationTotal = { residential: 0, mosque: 0 };
	let unmatched = 0;

	for (const r of relevant) {
		const key = r.conversion_type === 'mosque' ? 'mosque' : 'residential';
		nationTotal[key]++;

		const region = matchFeature(r.longitude, r.latitude, regionsGeo, 'tcRegion');
		if (region) {
			regions[region] ??= { residential: 0, mosque: 0 };
			regions[region][key]++;
		} else {
			unmatched++;
		}

		const district = matchFeature(r.longitude, r.latitude, districtsGeo, 'name');
		if (district) {
			districts[district] ??= { residential: 0, mosque: 0 };
			districts[district][key]++;
		}
	}

	log(`unmatched (no region polygon hit, e.g. offshore): ${unmatched}`);
	log(`nation: residential=${nationTotal.residential} mosque=${nationTotal.mosque}`);
	log(`regions with >=1 mosque: ${Object.entries(regions).filter(([, v]) => v.mosque > 0).length} / ${Object.keys(regions).length}`);
	log(`districts with >=1 mosque: ${Object.entries(districts).filter(([, v]) => v.mosque > 0).length} / ${Object.keys(districts).length}`);

	const out = { nation: nationTotal, regions, districts };
	const outPath = path.join(DATA_DIR, 'mosque-ratios.json');
	writeFileSync(outPath, JSON.stringify(out));
	log(`wrote ${path.relative(process.cwd(), outPath)}`);
}

main();
