#!/usr/bin/env node
// Rebuilds the boundary layers behind the choropleth map:
//   1. regions.json    — 11 UK regions/nations (England x9 + Scotland + Wales)
//   2. districts.json  — 380 GB local authority districts, used as the
//                        "zoom in" city/authority layer
//   3. nave-geo.json   — re-tagged with the matched district per city
//
// Sources are the UK-GeoJSON project (martinjc/UK-GeoJSON), which mirrors
// ONS/OS OpenData boundary releases as plain GeoJSON. Raw downloads are
// cached in scripts/.cache so re-runs (e.g. while tuning simplification)
// don't re-fetch multi-MB files every time.
//
// Usage:
//   node scripts/build-geo.mjs [--simplify-regions=8%] [--simplify-districts=4%] [--force]

import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const CACHE_DIR = path.join(__dirname, '.cache');
const DATA_DIR = path.join(__dirname, '../src/lib/data');
const MAPSHAPER_BIN = path.join(__dirname, '../node_modules/.bin/mapshaper');

const SOURCES = {
	regions: 'https://raw.githubusercontent.com/martinjc/UK-GeoJSON/master/json/electoral/gb/eer.json',
	districts: 'https://raw.githubusercontent.com/martinjc/UK-GeoJSON/master/json/administrative/gb/lad.json'
};

// EER (European Electoral Region) boundary names -> our region keys.
// England's 9 regions map 1:1; Wales and Scotland are each a single region
// in our dataset, which happens to line up with the EER's national units.
const EER_NAME_MAP = {
	'North East': 'North East',
	'North West': 'North West',
	'Yorkshire and The Humber': 'Yorkshire & Humber',
	'East Midlands': 'East Midlands',
	'West Midlands': 'West Midlands',
	Eastern: 'East of England',
	London: 'London',
	'South East': 'South East',
	'South West': 'South West',
	Wales: 'Wales',
	Scotland: 'Scotland'
};

const args = new Map(
	process.argv.slice(2).map((a) => {
		const [k, v] = a.replace(/^--/, '').split('=');
		return [k, v ?? true];
	})
);
const SIMPLIFY_REGIONS = args.get('simplify-regions') ?? '8%';
const SIMPLIFY_DISTRICTS = args.get('simplify-districts') ?? '4%';
const FORCE = args.get('force') === true;

function log(msg) {
	console.log(`[build-geo] ${msg}`);
}

async function download(url, cachePath) {
	if (existsSync(cachePath) && !FORCE) {
		log(`using cached ${path.basename(cachePath)}`);
		return;
	}
	log(`downloading ${url}`);
	const res = await fetch(url);
	if (!res.ok) throw new Error(`fetch failed (${res.status}) for ${url}`);
	const buf = Buffer.from(await res.arrayBuffer());
	writeFileSync(cachePath, buf);
	log(`saved ${(buf.length / 1024 / 1024).toFixed(1)}MB -> ${path.basename(cachePath)}`);
}

function mapshaper(inputPath, outputPath, simplifyPct) {
	execFileSync(
		MAPSHAPER_BIN,
		[
			inputPath,
			'-simplify',
			simplifyPct,
			'keep-shapes',
			'-clean',
			'-o',
			'format=geojson',
			'precision=0.0001',
			outputPath
		],
		{ stdio: 'inherit' }
	);
}

// Ray-casting point-in-polygon test; handles Polygon and MultiPolygon.
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
		// ring 0 is the outer boundary; any subsequent rings are holes.
		if (!pointInRing(lon, lat, rings[0])) continue;
		const inHole = rings.slice(1).some((hole) => pointInRing(lon, lat, hole));
		if (!inHole) return true;
	}
	return false;
}

function matchDistrict(lon, lat, districts) {
	for (const f of districts.features) {
		if (pointInFeature(lon, lat, f.geometry)) return f.properties;
	}
	return null;
}

async function main() {
	mkdirSync(CACHE_DIR, { recursive: true });
	mkdirSync(DATA_DIR, { recursive: true });

	const regionsRaw = path.join(CACHE_DIR, 'eer-raw.json');
	const districtsRaw = path.join(CACHE_DIR, 'lad-raw.json');
	await download(SOURCES.regions, regionsRaw);
	await download(SOURCES.districts, districtsRaw);

	// --- regions: simplify + relabel to our region keys -------------------
	const regionsSimplified = path.join(CACHE_DIR, 'regions-simplified.json');
	log(`simplifying regions (${SIMPLIFY_REGIONS} retained)…`);
	mapshaper(regionsRaw, regionsSimplified, SIMPLIFY_REGIONS);
	const regionsGeo = JSON.parse(readFileSync(regionsSimplified, 'utf8'));
	for (const f of regionsGeo.features) {
		const nm = f.properties?.EER13NM ?? '';
		f.properties = { tcRegion: EER_NAME_MAP[nm] ?? nm };
	}
	const regionsOut = path.join(DATA_DIR, 'regions.json');
	writeFileSync(regionsOut, JSON.stringify(regionsGeo));
	log(`wrote ${regionsGeo.features.length} regions -> ${path.relative(process.cwd(), regionsOut)}`);

	// --- districts: simplify + relabel -------------------------------------
	const districtsSimplified = path.join(CACHE_DIR, 'districts-simplified.json');
	log(`simplifying districts (${SIMPLIFY_DISTRICTS} retained)…`);
	mapshaper(districtsRaw, districtsSimplified, SIMPLIFY_DISTRICTS);
	const districtsGeo = JSON.parse(readFileSync(districtsSimplified, 'utf8'));
	for (const f of districtsGeo.features) {
		const p = f.properties ?? {};
		f.properties = { name: p.LAD13NM ?? p.name ?? '', code: p.LAD13CD ?? p.code ?? '' };
	}
	const districtsOut = path.join(DATA_DIR, 'districts.json');
	writeFileSync(districtsOut, JSON.stringify(districtsGeo));
	log(
		`wrote ${districtsGeo.features.length} districts -> ${path.relative(process.cwd(), districtsOut)}`
	);

	// --- tag each city in nave-geo.json with its matched district ---------
	const naveGeoPath = path.join(DATA_DIR, 'nave-geo.json');
	const naveGeo = JSON.parse(readFileSync(naveGeoPath, 'utf8'));
	let matched = 0;
	for (const city of naveGeo.cities) {
		const hit = matchDistrict(city.lon, city.lat, districtsGeo);
		if (hit) {
			city.district = hit.name;
			city.districtCode = hit.code;
			matched++;
		}
	}
	writeFileSync(naveGeoPath, JSON.stringify(naveGeo));
	log(
		`matched ${matched}/${naveGeo.cities.length} cities (${((matched / naveGeo.cities.length) * 100).toFixed(1)}%) to a district`
	);

	log('done.');
}

main().catch((err) => {
	console.error(err);
	process.exit(1);
});
