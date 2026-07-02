import { dash, regionData } from './state.svelte';
import { GEO, COUNTRY_ORDER, UK_TOTALS, type CityRecord } from './data/geo';
import { CATS, catColor, catLabel, catShortLabel } from './design/categories';

export interface LegendItem {
	label: string;
	color: string;
}
export interface MapTabVm {
	id: 'category' | 'density';
	label: string;
	active: boolean;
}
export interface RowVm {
	label: string;
	sub: string;
	color: string;
	go: () => void;
}
export interface CountryRowVm {
	name: string;
	count: string;
	active: boolean;
	chev: string;
	go: () => void;
	hover: () => void;
}
export interface BarVm {
	h: string;
	color: string;
}
export interface DonutSeg {
	color: string;
	dash: string;
	offset: string;
}
export interface DonutLeader {
	points: string;
	lp: string;
	tp: string;
	tf: string;
	align: 'left' | 'right';
	label: string;
	pct: string;
	color: string;
}

export function legendTitle(): string {
	return dash.mapMode === 'density' ? 'Site density' : 'Dominant conversion';
}

export function legend(): LegendItem[] {
	if (dash.mapMode === 'density') {
		return [
			{ label: 'Low', color: '#7a3d12' },
			{ label: '', color: '#b35d1f' },
			{ label: '', color: '#ee8434' },
			{ label: 'High', color: '#f79d5c' }
		];
	}
	return CATS.map((c) => ({ label: c.label, color: c.color }));
}

export function mapTabs(): MapTabVm[] {
	return [
		{ id: 'category', label: 'Category', active: dash.mapMode === 'category' },
		{ id: 'density', label: 'Density', active: dash.mapMode === 'density' }
	];
}

interface ResolvedSelection {
	kicker: string;
	name: string;
	n: number;
	cat: string;
	mix: number[];
	byRegion: string[] | null;
}

export function resolveSelection(): ResolvedSelection {
	const sel = dash.selection;
	if (sel.level === 'country' && GEO.countries[sel.key ?? '']) {
		const c = GEO.countries[sel.key as string];
		return {
			kicker: 'Country',
			name: sel.key as string,
			n: c.n,
			cat: c.cat,
			mix: c.mix,
			byRegion: c.regions.length > 1 ? c.regions : null
		};
	}
	if (sel.level === 'region' && regionData[sel.key ?? '']) {
		const r = regionData[sel.key as string];
		return { kicker: 'Region', name: sel.key as string, n: r.n, cat: r.cat, mix: r.mix, byRegion: null };
	}
	if (sel.level === 'city' && sel.data) {
		const c = sel.data;
		return { kicker: c.region, name: c.name, n: c.n, cat: c.cat, mix: c.mix, byRegion: null };
	}
    return {
		kicker: 'United Kingdom',
		name: 'United Kingdom',
		n: UK_TOTALS.n,
		cat: UK_TOTALS.cat,
		mix: UK_TOTALS.mix,
		byRegion: UK_TOTALS.regions
	};
}

export function bars(sel: ResolvedSelection): { bars: BarVm[]; caption: string } {
	if (sel.byRegion) {
		const arr = sel.byRegion
			.map((n) => ({ n, v: regionData[n] ? regionData[n].n : 0 }))
			.sort((a, b) => a.v - b.v);
		const mx = Math.max(...arr.map((x) => x.v), 1);
		return {
			bars: arr.map((x) => ({ h: `${Math.round(10 + (x.v / mx) * 90)}%`, color: 'var(--gold)' })),
			caption: 'by region'
		};
	}
	const mx = Math.max(...(sel.mix || [1]), 1);
	return {
		bars: (sel.mix || []).map((v, i) => ({
			h: `${Math.round(6 + (v / mx) * 94)}%`,
			color: CATS[i]?.color ?? '#ae8799'
		})),
		caption: 'by conversion'
	};
}

export function ringSegments(mix: number[], r: number): DonutSeg[] {
	const total = mix.reduce((a, b) => a + b, 0) || 1;
	const C = 2 * Math.PI * r;
	let acc = 0;
	return mix.map((v, i) => {
		const len = (v / total) * C;
		const seg: DonutSeg = {
			color: CATS[i]?.color ?? '#ae8799',
			dash: `${len.toFixed(2)} ${C.toFixed(2)}`,
			offset: (-acc).toFixed(2)
		};
		acc += len;
		return seg;
	});
}

export function donutForMix(mix: number[]) {
	const mixTotal = mix.reduce((a, b) => a + b, 0) || 1;
	const vbW = 224,
		vbH = 122,
		dcx = 112,
		dcy = 62,
		dR = 32,
		dStroke = 24,
		dOuter = dR + dStroke / 2;
	const C = 2 * Math.PI * dR;
	let acc = 0;
	const segs: DonutSeg[] = mix.map((v, i) => {
		const len = (v / mixTotal) * C;
		const seg: DonutSeg = {
			color: CATS[i]?.color ?? '#ae8799',
			dash: `${len.toFixed(2)} ${C.toFixed(2)}`,
			offset: (-acc).toFixed(2)
		};
		acc += len;
		return seg;
	});

	let cumF = 0;
	const segList: { i: number; mid: number; share: number; color: string; label: string }[] = [];
	mix.forEach((v, i) => {
		if (v > 0) {
			const frac = v / mixTotal;
			segList.push({
				i,
				mid: cumF + frac / 2,
				share: Math.round(frac * 100),
				color: CATS[i]?.color ?? '#ae8799',
				label: catShortLabel(GEO.cats[i])
			});
			cumF += frac;
		}
	});
	const ptOf = (frac: number, r: number) => {
		const a = ((-90 + frac * 360) * Math.PI) / 180;
		return { x: dcx + r * Math.cos(a), y: dcy + r * Math.sin(a), c: Math.cos(a) };
	};
	const rightS: typeof segList = [],
		leftS: typeof segList = [];
	segList.forEach((s) => (ptOf(s.mid, 1).c >= 0 ? rightS : leftS).push(s));
	const assign = (arr: typeof segList, side: 'r' | 'l'): DonutLeader[] => {
		arr.sort((a, b) => ptOf(a.mid, 1).y - ptOf(b.mid, 1).y);
		const n = arr.length,
			top = 10,
			bot = vbH - 10,
			step = n > 1 ? (bot - top) / (n - 1) : 0;
		const kneeX = side === 'r' ? 158 : 66,
			endX = side === 'r' ? 160 : 64;
		return arr.map((s, k) => {
			const ly = n > 1 ? top + step * k : dcy;
			const ring = ptOf(s.mid, dOuter);
			return {
				points: `${ring.x.toFixed(1)},${ring.y.toFixed(1)} ${kneeX},${ly.toFixed(1)} ${endX},${ly.toFixed(1)}`,
				lp: ((endX / vbW) * 100).toFixed(2),
				tp: ((ly / vbH) * 100).toFixed(2),
				tf: side === 'r' ? 'translateY(-50%)' : 'translate(-100%,-50%)',
				align: side === 'r' ? 'left' : 'right',
				label: s.label,
				pct: s.share > 0 ? `${s.share}%` : '<1%',
				color: s.color
			};
		});
	};
	const donutLeaders: DonutLeader[] = [...assign(rightS, 'r'), ...assign(leftS, 'l')];
	return { segs, donutLeaders };
}

export interface HoverInfo {
	kicker: string;
	name: string;
	cat: string;
	color: string;
	index: number;
	bar: string;
	sites: string;
}

export function hoverInfo(sel: ResolvedSelection, topShare: number): HoverInfo {
	const hr = dash.hoverRegion;
	const hd = hr ? regionData[hr] : null;
	if (hd) {
		return {
			kicker: 'Region',
			name: hr as string,
			cat: catLabel(hd.cat),
			color: dash.mapMode === 'density' ? '#ee8434' : catColor(hd.cat),
			index: Math.round(hd.d * 100),
			bar: `${Math.round(hd.d * 100)}%`,
			sites: hd.n.toLocaleString()
		};
	}
	return {
		kicker: sel.kicker,
		name: sel.name,
		cat: `${catLabel(sel.cat)} · ${topShare}%`,
		color: catColor(sel.cat),
		index: topShare,
		bar: `${topShare}%`,
		sites: (sel.n || 0).toLocaleString()
	};
}

export function searchCountries(): CountryRowVm[] {
	return COUNTRY_ORDER.filter((n) => GEO.countries[n]).map((n) => ({
		name: n,
		count: GEO.countries[n].n.toLocaleString(),
		active: dash.openCountry === n,
		chev: dash.openCountry === n ? '▾' : '▸',
		go: () => dash.chooseCountry(n),
		hover: () => dash.hoverCountry(n)
	}));
}

export function subPanel(): { title: string; items: RowVm[] } {
	const cn = dash.openCountry;
	if (!cn || !GEO.countries[cn]) return { title: '', items: [] };
	const c = GEO.countries[cn];
	if (c.regions.length > 1) {
		return {
			title: cn,
			items: c.regions.map((rn) => ({
				label: rn,
				sub: `${regionData[rn] ? regionData[rn].n.toLocaleString() : '0'} sites`,
				color: catColor(regionData[rn] ? regionData[rn].cat : 'unknown'),
				go: () => dash.chooseRegion(rn)
			}))
		};
	}
	return {
		title: cn,
		items: (GEO.cities || [])
			.filter((ct) => ct.nation === cn)
			.slice(0, 10)
			.map((ct) => ({
				label: ct.name,
				sub: `${ct.n.toLocaleString()} sites`,
				color: catColor(ct.cat),
				go: () => dash.chooseCity(ct)
			}))
	};
}

export function searchResults(): RowVm[] {
	const q = (dash.searchQuery || '').trim().toLowerCase();
	if (!q) return [];
	const rMatch: RowVm[] = Object.keys(regionData)
		.filter((n) => n.toLowerCase().includes(q))
		.map((n) => ({
			label: n,
			sub: `Region · ${regionData[n].n.toLocaleString()}`,
			color: catColor(regionData[n].cat),
			go: () => dash.chooseRegion(n)
		}));
	const cMatch: RowVm[] = (GEO.cities || [])
		.filter((ct) => ct.name.toLowerCase().includes(q))
		.slice(0, 8)
		.map((ct) => ({
			label: ct.name,
			sub: `${ct.region} · ${ct.n.toLocaleString()}`,
			color: catColor(ct.cat),
			go: () => dash.chooseCity(ct)
		}));
	return rMatch.concat(cMatch).slice(0, 10);
}