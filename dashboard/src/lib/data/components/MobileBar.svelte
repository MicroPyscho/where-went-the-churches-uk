<script lang="ts">
	import { dash } from '$lib/state.svelte';
	import { resolveSelection, hoverInfo, ringSegments, legend, mapTabs } from '$lib/viewmodel';

	let sel = $derived(resolveSelection());
	let topShare = $derived(
		sel.n ? Math.round(((sel.mix ? Math.max(...sel.mix) : 0) / sel.n) * 100) : 0
	);
	let hover = $derived(hoverInfo(sel, topShare));
	let ringSegs = $derived(ringSegments(sel.mix || [], 46));
	let items = $derived(legend());
	let tabs = $derived(mapTabs());
</script>

<div class="mobile-bar">
	<div class="glass seg stat-seg">
		<p class="kicker">{hover.kicker}</p>
		<p class="stat-name">{hover.name}</p>
		<div class="stat-row">
			<span class="swatch" style="background:{hover.color};"></span>
			<span class="stat-cat">{hover.cat}</span>
		</div>
		<div class="stat-sites">{hover.sites}<span class="stat-sites-label"> sites</span></div>
	</div>

	<div class="glass seg donut-seg">
		<svg viewBox="0 0 120 120" class="mini-donut">
			<circle cx="60" cy="60" r="46" fill="none" stroke="var(--bg3)" stroke-width="13"></circle>
			{#each ringSegs as s, i (i)}
				<circle
					cx="60"
					cy="60"
					r="46"
					fill="none"
					stroke={s.color}
					stroke-width="13"
					stroke-dasharray={s.dash}
					stroke-dashoffset={s.offset}
					transform="rotate(-90 60 60)"
				></circle>
			{/each}
		</svg>
	</div>

	<div class="glass seg legend-seg">
		{#each items as g, i (i)}
			<span class="legend-chip"><span class="chip" style="background:{g.color};"></span>{g.label}</span>
		{/each}
	</div>

	<div class="glass seg mode-seg">
		{#each tabs as t (t.id)}
			<button
				class="mode-btn"
				style="background:{t.active ? 'var(--gold)' : 'transparent'};color:{t.active
					? '#0e1220'
					: 'var(--txd)'};"
				onclick={() => dash.setMapMode(t.id)}>{t.label}</button
			>
		{/each}
	</div>

	<div class="glass seg zoom-seg">
		<button class="zoom-btn" aria-label="Zoom in" onclick={() => dash.zoomBy(0.5)}>+</button>
		<button class="zoom-btn" aria-label="Zoom out" onclick={() => dash.zoomBy(-0.5)}>−</button>
	</div>
</div>

<style>
	.mobile-bar {
		display: none;
	}

	@media (max-width: 720px) {
		.mobile-bar {
			display: flex;
			position: fixed;
			left: 0;
			right: 0;
			bottom: 0;
			z-index: 900;
			gap: 8px;
			padding: 10px 10px calc(10px + env(safe-area-inset-bottom, 0px));
			overflow-x: auto;
			background: var(--head);
			backdrop-filter: blur(18px);
			-webkit-backdrop-filter: blur(18px);
			border-top: 1px solid var(--bd);
		}
		.seg {
			flex-shrink: 0;
			border-radius: 14px;
		}
		.stat-seg {
			width: 160px;
			padding: 10px 12px;
		}
		.stat-name {
			font-family: var(--font-display);
			font-weight: 600;
			font-size: 14px;
			margin: 0 0 6px;
			color: var(--tx);
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		}
		.stat-row {
			display: flex;
			align-items: center;
			gap: 6px;
			margin-bottom: 6px;
		}
		.stat-row .swatch {
			width: 8px;
			height: 8px;
			border-radius: 2px;
		}
		.stat-cat {
			font-size: 11px;
			color: var(--txd);
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		}
		.stat-sites {
			font-family: var(--font-display);
			font-weight: 700;
			font-size: 16px;
			color: var(--tx);
		}
		.stat-sites-label {
			font-family: var(--font-sans);
			font-weight: 400;
			font-size: 10px;
			color: var(--txf);
		}
		.donut-seg {
			width: 66px;
			display: flex;
			align-items: center;
			justify-content: center;
			padding: 6px;
		}
		.mini-donut {
			width: 52px;
			height: 52px;
		}
		.legend-seg {
			display: flex;
			flex-wrap: nowrap;
			align-items: center;
			gap: 10px;
			padding: 0 14px;
			overflow-x: auto;
			width: 220px;
		}
		.legend-chip {
			display: inline-flex;
			align-items: center;
			gap: 5px;
			font-size: 10.5px;
			color: var(--txd);
			white-space: nowrap;
		}
		.chip {
			width: 11px;
			height: 7px;
			border-radius: 2px;
			flex-shrink: 0;
		}
		.mode-seg {
			display: flex;
			flex-direction: column;
			padding: 3px;
			border-radius: 999px;
			justify-content: center;
		}
		.mode-btn {
			border: none;
			border-radius: 999px;
			padding: 6px 12px;
			cursor: pointer;
			font-size: 11px;
			font-weight: 600;
		}
		.zoom-seg {
			display: flex;
			flex-direction: column;
			padding: 0;
			overflow: hidden;
		}
		.zoom-btn {
			width: 40px;
			height: 34px;
			border: none;
			background: transparent;
			cursor: pointer;
			color: var(--tx);
			font-size: 18px;
			line-height: 1;
		}
		.zoom-btn:first-child {
			border-bottom: 1px solid var(--glassbd);
		}
	}
</style>
