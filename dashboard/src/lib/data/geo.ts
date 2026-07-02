import raw from './nave-geo.json';

export interface CityRecord {
	name: string;
	region: string;
	nation: string;
	n: number;
	cat: string;
	mix: number[];
	lat: number;
	lon: number;
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

// maps EER13NM boundary names -> our region keys
export const EER_NAME_MAP: Record<string, string> = {
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

export const COUNTRY_ORDER = ['England', 'Scotland', 'Wales'];

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