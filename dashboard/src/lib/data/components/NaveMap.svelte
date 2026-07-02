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
		if (choro) {
			try {
				map.removeLayer(choro);
			} catch {
				/* ignore */
			}
		}
		regionLayers = {};
		const gj = structuredClone(eerRegions) as GeoJSON.FeatureCollection;
		for (const f of gj.features) {
			const nm = (f.properties as any)?.EER13NM ?? '';
			(f.properties as any).tcRegion = EER_NAME_MAP[nm] ?? nm;
		}
		choro = L.geoJSON(gj, {
			style: (f: any) => choroStyle(f.properties.tcRegion),
			onEachFeature: (f: any, layer: any) => {
				const region = f.properties.tcRegion;
				const data = regionData[region];
				regionLayers[region] = layer;
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

	function applySelection() {
		if (!map || !L) return;
		refreshChoro();
		if (cityMarker) {
			try {
				map.removeLayer(cityMarker);
			} catch {
				/* ignore */
			}
			cityMarker = null;
		}
		const s = dash.selection;
		if (s.level === 'city' && s.data && s.data.lat != null) {
			const col = catColor(s.data.cat);
			try {
				cityMarker = L.circleMarker([s.data.lat, s.data.lon], {
					radius: 9,
					fillColor: col,
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
			} catch {
				/* ignore */
			}
			try {
				map.setView([s.data.lat, s.data.lon], 9.5, { animate: true, duration: 0.8 });
			} catch {
				try {
					map.setView([s.data.lat, s.data.lon], 9.5);
				} catch {
					/* ignore */
				}
			}
			return;
		}
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
			maxZoom: 12,
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

		onResize = () => {
			if (map) map.invalidateSize();
		};
		window.addEventListener('resize', onResize);
	});

	onDestroy(() => {
		if (host && wheelPan) host.removeEventListener('wheel', wheelPan);
		if (onResize) window.removeEventListener('resize', onResize);
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
