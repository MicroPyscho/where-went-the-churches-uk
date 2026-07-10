<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import type { GeoJSON as LGeoJSON, Map as LeafletMap, TileLayer, Layer, CircleMarker } from 'leaflet';
	import { dash, regionData } from '$lib/state.svelte';
	import { catColor, densityColor } from '$lib/design/categories';
	import regionsGeo from '$lib/data/regions.json';

	// districts.json is ~460KB — only fetched once the map is actually
	// zoomed/selected in far enough to need it, and code-split by Vite.
	const DISTRICT_ZOOM_THRESHOLD = 8;

	let host: HTMLDivElement;
	let map: LeafletMap | null = null;
	let tile: TileLayer | null = null;
	let choro: LGeoJSON | null = null;
	let districtsLayer: LGeoJSON | null = null;
	let districtLayersByCode: Record<string, Layer> = {};
	let highlightedDistrict: string | null = null;
	let cityMarker: CircleMarker | null = null;
	let districtsLoading: Promise<GeoJSON.FeatureCollection> | null = null;
	let fitted = false;
	let L: typeof import('leaflet');
	let wheelPan: ((e: WheelEvent) => void) | null = null;
	let onResize: (() => void) | null = null;
	let onZoom: (() => void) | null = null;

	function tileUrl(theme: string) {
		return theme === 'dark'
			? 'https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png'
			: 'https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png';
	}

	function catLabelFor(id: string) {
		const labels: Record<string, string> = {
			residential: 'Residential',
			other_christian: 'Other Christian use',
			education: 'Education',
			hospitality: 'Hospitality',
			commercial: 'Commercial',
			community: 'Community',
			arts_culture: 'Arts & Culture',
			unknown: 'Other / unrecorded'
		};
		return labels[id] ?? 'Other';
	}

	// ── region choropleth ────────────────────────────────────────────────
	function choroStyle(region: string) {
		const data = regionData[region];
		const dark = dash.theme === 'dark';
		const active = dash.activeRegions();
		const dimmed = !!(active && !active.has(region));
		if (!data) {
			return {
				color: '#ae8799',
				weight: 1,
				opacity: dimmed ? 0.12 : 0.4,
				fillColor: '#ae8799',
				fillOpacity: dimmed ? 0.02 : dark ? 0.05 : 0.06,
				className: 'tc-region'
			};
		}
		let style: Record<string, unknown>;
		if (dash.mapMode === 'density') {
			// discrete 5-step ramp — matches the density legend swatches exactly,
			// rather than a single hue whose opacity is hard to read at a glance.
			const col = densityColor(data.d);
			style = {
				color: col,
				weight: 1.8,
				opacity: dark ? 1 : 0.9,
				fillColor: col,
				fillOpacity: dark ? 0.62 : 0.66,
				className: 'tc-region'
			};
		} else {
			const col = catColor(data.cat);
			style = {
				color: col,
				weight: 1.8,
				opacity: dark ? 1 : 0.9,
				fillColor: col,
				fillOpacity: dark ? 0.42 : 0.46,
				className: 'tc-region'
			};
		}
		if (dimmed) {
			style.fillOpacity = dark ? 0.05 : 0.06;
			style.opacity = 0.18;
			style.weight = 0.6;
		} else if (active) {
			style.weight = 2.6;
			style.fillOpacity = Math.min(0.72, (style.fillOpacity as number) + 0.14);
		}
		return style;
	}

	function refreshChoro() {
		if (!choro) return;
		choro.eachLayer((l: any) => {
			try {
				l.setStyle(choroStyle(l.feature.properties.tcRegion));
			} catch {
				/* ignore */
			}
		});
	}

	function drawChoro() {
		if (!map || !L) return;
		choro = L.geoJSON(regionsGeo as GeoJSON.FeatureCollection, {
			style: (f: any) => choroStyle(f.properties.tcRegion),
			onEachFeature: (f: any, layer: any) => {
				const region = f.properties.tcRegion;
				const data = regionData[region];
				if (data) {
					layer.bindTooltip(
						`<b>${region}</b><br>${catLabelFor(data.cat)} · ${data.n.toLocaleString()} sites`,
						{ className: 'tc-tip', sticky: true }
					);
				}
				layer.on('mouseover', function (this: any) {
					this.setStyle({
						weight: 3.2,
						fillOpacity: Math.min(0.72, (choroStyle(region).fillOpacity as number) + 0.18)
					});
					this.bringToFront();
					dash.setHover(region);
				});
				layer.on('mouseout', function (this: any) {
					choro!.resetStyle(this);
					dash.clearHover();
				});
				layer.on('click', () => dash.chooseRegion(region));
			}
		}).addTo(map);
		choro.bringToBack();
		if (!fitted) {
			fitted = true;
			try {
				map.fitBounds(choro.getBounds(), { paddingTopLeft: [40, 70], paddingBottomRight: [40, 60] });
			} catch {
				/* ignore */
			}
		}
		applySelection();
	}

	// ── local authority districts: the "zoom in" layer ─────────────────────
	function districtStyle(code: string) {
		const dark = dash.theme === 'dark';
		if (code === highlightedDistrict) {
			const cat = dash.selection.data?.cat;
			const col = catColor(cat);
			return { color: col, weight: 2.2, opacity: 1, fillColor: col, fillOpacity: dark ? 0.38 : 0.42 };
		}
		return {
			color: dark ? 'rgba(229,229,235,.45)' : 'rgba(40,50,60,.4)',
			weight: 1,
			opacity: 1,
			// a literal 0 fillOpacity (or fillColor:'transparent') isn't
			// hit-tested by the browser, so clicks fall through to the
			// choropleth region layer underneath instead of selecting this
			// district — keep the fill effectively invisible but non-zero so
			// every district stays clickable.
			fillColor: '#000000',
			fillOpacity: 0.001
		};
	}

	function loadDistricts(): Promise<GeoJSON.FeatureCollection> {
		if (!districtsLoading) {
			districtsLoading = import('$lib/data/districts.json').then(
				(mod) => mod.default as unknown as GeoJSON.FeatureCollection
			);
		}
		return districtsLoading;
	}

	async function ensureDistrictsLayer() {
		if (!map || !L || districtsLayer) return;
		const gj = await loadDistricts();
		if (!map || !L) return; // component may have unmounted while awaiting
		districtLayersByCode = {};
		districtsLayer = L.geoJSON(gj, {
			style: (f: any) => districtStyle(f.properties.code),
			onEachFeature: (f: any, layer: any) => {
				districtLayersByCode[f.properties.code] = layer;
				layer.bindTooltip(f.properties.name, { className: 'tc-tip', sticky: true });
				layer.on('click', (e: any) => {
					dash.chooseDistrict(f.properties.code, f.properties.name, e.latlng.lat, e.latlng.lng);
				});
			}
		});
		syncDistrictsVisibility();
	}

	function refreshDistrictStyles() {
		if (!districtsLayer) return;
		districtsLayer.eachLayer((l: any) => {
			try {
				l.setStyle(districtStyle(l.feature.properties.code));
				if (l.feature.properties.code === highlightedDistrict) l.bringToFront();
			} catch {
				/* ignore */
			}
		});
	}

	function syncDistrictsVisibility() {
		if (!map || !districtsLayer) return;
		const shouldShow = map.getZoom() >= DISTRICT_ZOOM_THRESHOLD || !!highlightedDistrict;
		const isShown = map.hasLayer(districtsLayer);
		if (shouldShow && !isShown) districtsLayer.addTo(map);
		else if (!shouldShow && isShown) map.removeLayer(districtsLayer);
	}

	// ── selection (drill-down) ──────────────────────────────────────────────
	async function applySelection() {
		if (!map || !L) return;
		refreshChoro();
		const s = dash.selection;

		if (cityMarker) {
			try {
				map.removeLayer(cityMarker);
			} catch {
				/* ignore */
			}
			cityMarker = null;
		}

		if (s.level === 'city' && s.data && s.data.lat != null) {
			await ensureDistrictsLayer();
			highlightedDistrict = s.data.districtCode ?? null;
			refreshDistrictStyles();
			syncDistrictsVisibility();

			const districtLayer = highlightedDistrict ? districtLayersByCode[highlightedDistrict] : null;
			try {
				if (districtLayer) {
					map.fitBounds((districtLayer as any).getBounds(), { padding: [40, 40], animate: true });
				} else {
					// no matched district (e.g. an island/offshore point) — fall
					// back to a plain marker rather than showing nothing.
					cityMarker = L.circleMarker([s.data.lat, s.data.lon], {
						radius: 9,
						fillColor: catColor(s.data.cat),
						color: dash.theme === 'dark' ? '#fff' : '#0d1017',
						weight: 2,
						opacity: 1,
						fillOpacity: 1
					}).addTo(map);
					cityMarker.bindTooltip(`<b>${s.data.name}</b><br>${s.data.n.toLocaleString()} sites`, {
						className: 'tc-tip',
						direction: 'top',
						offset: [0, -8]
					});
					map.setView([s.data.lat, s.data.lon], 10.5, { animate: true });
				}
			} catch {
				/* ignore */
			}
			return;
		}

		highlightedDistrict = null;
		refreshDistrictStyles();
		syncDistrictsVisibility();

		const active = dash.activeRegions();
		if (!active) {
			try {
				map.setView([54.6, -3.4], 5.25, { animate: true });
			} catch {
				/* ignore */
			}
			return;
		}
		const names = [...active].filter((n) => regionData[n] && regionData[n].lat != null);
		if (names.length) {
			let la = 0,
				lo = 0,
				wt = 0;
			for (const n of names) {
				const w = regionData[n].n || 1;
				la += regionData[n].lat * w;
				lo += regionData[n].lon * w;
				wt += w;
			}
			const center: [number, number] = [la / wt, lo / wt];
			let zoom: number;
			if (s.level === 'region') zoom = s.key === 'London' ? 8.5 : 7.2;
			else zoom = names.length > 1 ? 5.9 : 6.2;
			try {
				map.setView(center, zoom, { animate: true });
			} catch {
				/* ignore */
			}
		}
	}

	onMount(async () => {
		L = await import('leaflet');
		map = L.map(host, {
			zoomControl: false,
			attributionControl: false,
			dragging: true,
			scrollWheelZoom: false,
			doubleClickZoom: false,
			boxZoom: false,
			keyboard: false,
			touchZoom: true,
			minZoom: 4,
			maxZoom: 13,
			zoomSnap: 0.25
		});
		map.setView([54.6, -3.4], 5.3);
		tile = L.tileLayer(tileUrl(dash.theme), {
			subdomains: 'abcd',
			maxZoom: 19,
			crossOrigin: true,
			attribution: '&copy; OpenStreetMap, &copy; CARTO'
		}).addTo(map);
		dash.mapInstance = map;

		wheelPan = (e: WheelEvent) => {
			if (e.ctrlKey) return;
			e.preventDefault();
			map!.panBy([e.deltaX, e.deltaY], { animate: false });
		};
		host.addEventListener('wheel', wheelPan, { passive: false });

		drawChoro();

		// past the threshold zoom, load (once) and show the district layer
		// for real geographic context instead of a flat basemap
		onZoom = () => {
			if (!map) return;
			if (map.getZoom() >= DISTRICT_ZOOM_THRESHOLD) ensureDistrictsLayer();
			syncDistrictsVisibility();
		};
		map.on('zoomend', onZoom);

		onResize = () => {
			if (map) map.invalidateSize();
		};
		window.addEventListener('resize', onResize);
	});

	onDestroy(() => {
		if (host && wheelPan) host.removeEventListener('wheel', wheelPan);
		if (onResize) window.removeEventListener('resize', onResize);
		if (map && onZoom) map.off('zoomend', onZoom);
		if (map) {
			try {
				map.remove();
			} catch {
				/* ignore */
			}
		}
		dash.mapInstance = null;
	});

	$effect(() => {
		const _t = dash.theme;
		if (tile) tile.setUrl(tileUrl(_t));
		refreshChoro();
		refreshDistrictStyles();
	});
	$effect(() => {
		const _m = dash.mapMode;
		refreshChoro();
	});
	$effect(() => {
		const _s = dash.selection;
		applySelection();
	});
</script>

<div bind:this={host} class="tc-poster-map" style="position:absolute;inset:0;"></div>
