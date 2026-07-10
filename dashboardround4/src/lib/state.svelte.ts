import { browser } from '$app/environment';
import type { Map as LeafletMap } from 'leaflet';
import { GEO, regionData, DISTRICT_DATA, type CityRecord } from '$lib/data/geo';

export type ThemeName = 'dark' | 'light';
export type MapMode = 'category' | 'density';
export type SelectionLevel = 'uk' | 'country' | 'region' | 'city';

export interface Selection {
	level: SelectionLevel;
	key: string | null;
	data?: CityRecord;
}

function readStoredTheme(): ThemeName {
	if (!browser) return 'dark';
	try {
		const s = localStorage.getItem('tc-theme');
		if (s === 'dark' || s === 'light') return s;
	} catch {
		/* ignore */
	}
	return 'dark';
}

class DashboardState {
	theme = $state<ThemeName>(readStoredTheme());
	mapMode = $state<MapMode>('category');
	hoverRegion = $state<string | null>(null);
	selection = $state<Selection>({ level: 'uk', key: null });
	searchQuery = $state('');
	searchOpen = $state(false);
	openCountry = $state<string | null>(null);

	// imperative, non-reactive handle to the live Leaflet map
	mapInstance: LeafletMap | null = null;

	toggleTheme() {
		this.theme = this.theme === 'dark' ? 'light' : 'dark';
		if (browser) {
			try {
				localStorage.setItem('tc-theme', this.theme);
			} catch {
				/* ignore */
			}
		}
	}

	setMapMode(mode: MapMode) {
		this.mapMode = mode;
	}

	openSearch() {
		this.searchOpen = true;
	}
	closeSearch() {
		this.searchOpen = false;
		this.openCountry = null;
	}
	onQuery(v: string) {
		this.searchQuery = v;
		this.searchOpen = true;
		this.openCountry = null;
	}
	hoverCountry(name: string) {
		this.openCountry = name;
	}
	chooseCountry(name: string) {
		this.selection = { level: 'country', key: name };
		this.openCountry = name;
	}
	chooseRegion(name: string) {
		this.selection = { level: 'region', key: name };
		this.searchOpen = false;
		this.openCountry = null;
		this.searchQuery = '';
	}
	chooseCity(city: CityRecord) {
		this.selection = { level: 'city', key: `${city.name}|${city.region}`, data: city };
		this.searchOpen = false;
		this.openCountry = null;
		this.searchQuery = '';
	}
	// clicking a district directly on the map (rather than picking a named
	// city from search) — resolves to the same aggregated district stats
	// the mosque-ratio card already keys off, so every clicked place responds.
	chooseDistrict(code: string, name: string, lat: number, lon: number) {
		const d = DISTRICT_DATA[code];
		const city: CityRecord = {
			name: d?.name ?? name,
			region: d?.region ?? '',
			nation: d?.nation ?? '',
			n: d?.n ?? 0,
			cat: d?.cat ?? 'unknown',
			mix: d?.mix ?? Array(GEO.cats.length).fill(0),
			lat,
			lon,
			district: d?.name ?? name,
			districtCode: code
		};
		this.selection = { level: 'city', key: `district|${code}`, data: city };
		this.searchOpen = false;
		this.openCountry = null;
		this.searchQuery = '';
	}
	clearSelection() {
		this.selection = { level: 'uk', key: null };
		this.searchOpen = false;
		this.openCountry = null;
		this.searchQuery = '';
	}

	setHover(r: string | null) {
		if (this.hoverRegion !== r) this.hoverRegion = r;
	}
	clearHover() {
		if (this.hoverRegion !== null) this.hoverRegion = null;
	}

	zoomBy(delta: number) {
		if (this.mapInstance) this.mapInstance.setZoom(this.mapInstance.getZoom() + delta);
	}

	activeRegions(): Set<string> | null {
		const s = this.selection;
		if (!s || s.level === 'uk') return null;
		if (s.level === 'country') return new Set(GEO.countries[s.key ?? '']?.regions ?? []);
		if (s.level === 'region') return new Set([s.key ?? '']);
		if (s.level === 'city') return new Set([s.data?.region ?? '']);
		return null;
	}
}

export const dash = new DashboardState();
export { regionData };
