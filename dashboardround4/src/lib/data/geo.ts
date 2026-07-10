import raw from './nave-geo.json';
import mosqueRatiosRaw from './mosque-ratios.json';

export interface CityRecord {
	name: string;
	region: string;
	nation: string;
	n: number;
	cat: string;
	mix: number[];
	lat: number;
	lon: number;
	district?: string;
	districtCode?: string;
}

export interface RegionRaw {
	n: number;
	nation: string;
	cat: string;
	mix: number[];
	lat: number;
	lon: number;
}

export interface CountryRaw {
	n: number;
	cat: string;
	mix: number[];
	regions: string[];
}

export interface NaveGeo {
	cats: string[];
	countries: Record<string, CountryRaw>;
	regions: Record<string, RegionRaw>;
	cities: CityRecord[];
}

export const GEO = raw as unknown as NaveGeo;

export interface RegionComputed {
	d: number;
	cat: string;
	n: number;
	mix: number[];
	lat: number;
	lon: number;
	nation: string;
}

function buildRegionData(): Record<string, RegionComputed> {
	const out: Record<string, RegionComputed> = {};
	const ns = Object.values(GEO.regions).map((r) => r.n);
	const maxN = ns.length ? Math.max(...ns) : 1;
	for (const [name, r] of Object.entries(GEO.regions)) {
		out[name] = {
			d: +(r.n / maxN).toFixed(3),
			cat: r.cat,
			n: r.n,
			mix: r.mix,
			lat: r.lat,
			lon: r.lon,
			nation: r.nation
		};
	}
	return out;
}

export const regionData: Record<string, RegionComputed> = buildRegionData();

export interface DistrictComputed {
	name: string;
	region: string;
	nation: string;
	n: number;
	cat: string;
	mix: number[];
}

// Local-authority-district aggregates, derived by summing the (already
// correctly categorised) named-city records that fall inside each district —
// not re-derived from the raw CSV, so there's no risk of a taxonomy mismatch
// with the rest of the dataset. Lets a map click on any district resolve to
// real stats even though the district boundary layer itself carries no
// conversion data of its own.
function buildDistrictData(): Record<string, DistrictComputed> {
	const out: Record<string, DistrictComputed> = {};
	for (const city of GEO.cities) {
		if (!city.districtCode) continue;
		const code = city.districtCode;
		if (!out[code]) {
			out[code] = {
				name: city.district ?? code,
				region: city.region,
				nation: city.nation,
				n: 0,
				cat: 'unknown',
				mix: Array(GEO.cats.length).fill(0)
			};
		}
		out[code].n += city.n;
		city.mix.forEach((v, i) => (out[code].mix[i] += v));
	}
	for (const code in out) {
		const mix = out[code].mix;
		let bi = 0;
		mix.forEach((v, i) => {
			if (v > mix[bi]) bi = i;
		});
		out[code].cat = GEO.cats[bi] ?? 'unknown';
	}
	return out;
}

export const DISTRICT_DATA: Record<string, DistrictComputed> = buildDistrictData();

export const COUNTRY_ORDER = ['England', 'Scotland', 'Wales'];

// Coordinate-derived residential:mosque counts (see
// scripts/build-mosque-ratios.mjs) — the CSV's own region/nation columns are
// blank for every row, so these are computed by matching each record's real
// lat/lon against the region and district boundary polygons.
export interface MosqueCount {
	residential: number;
	mosque: number;
}
export interface MosqueRatios {
	nation: MosqueCount;
	regions: Record<string, MosqueCount>;
	districts: Record<string, MosqueCount>;
}
export const MOSQUE_RATIOS = mosqueRatiosRaw as MosqueRatios;

export const UK_TOTALS = (() => {
	const mix = Array(8).fill(0);
	let tot = 0;
	for (const r of Object.values(regionData)) {
		tot += r.n;
		if (r.mix) r.mix.forEach((v, i) => (mix[i] += v));
	}
	let bi = 0;
	mix.forEach((v, i) => {
		if (v > mix[bi]) bi = i;
	});
	return { n: tot, mix, cat: GEO.cats[bi] ?? 'unknown', regions: Object.keys(regionData) };
})();
