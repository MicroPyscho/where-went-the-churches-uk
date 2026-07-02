<script lang="ts">
	import { dash } from '$lib/state.svelte';
	import { resolveSelection, hoverInfo, donutForMix, mapTabs } from '$lib/viewmodel';

	let sel = $derived(resolveSelection());
	let topShare = $derived(
		sel.n ? Math.round(((sel.mix ? Math.max(...sel.mix) : 0) / sel.n) * 100) : 0
	);
	let hover = $derived(hoverInfo(sel, topShare));
	let donut = $derived(donutForMix(sel.mix || []));
	let tabs = $derived(mapTabs());
</script>

<div class="rail">
	<!-- hover / selection card -->
	<div class="glass card">
		<p class="kicker">{hover.kicker}</p>
		<p class="entity-name">{hover.name}</p>
		<div class="cat-row">
			<span class="swatch" style="background:{hover.color};box-shadow:0 0 8px {hover.color};"
			></span>
			<span class="cat-label">{hover.cat}</span>
		</div>
		<div class="index-row">
			<span class="index-label">Conversion index</span>
			<span class="index-value">{hover.index}</span>
		</div>
		<div class="index-track">
			<div class="index-fill" style="width:{hover.bar};"></div>
		</div>
		<div class="sites-row">
			<span class="index-label">Sites mapped</span>
			<span class="sites-value">{hover.sites}</span>
		</div>
	</div>

	<!-- donut -->
	<div class="glass donut-card">
		<p class="kicker" style="text-align:center;margin-bottom:2px;">Church converted to</p>
		<div class="donut-wrap">
			<svg viewBox="0 0 224 122" class="donut-svg">
				<g transform="rotate(-90 112 62)">
					<circle cx="112" cy="62" r="32" fill="none" stroke="var(--bg3)" stroke-width="24"
					></circle>
					{#each donut.segs as s, i (i)}
						<circle
							cx="112"
							cy="62"
							r="32"
							fill="none"
							stroke={s.color}
							stroke-width="24"
							stroke-dasharray={s.dash}
							stroke-dashoffset={s.offset}
							class="donut-seg"
						></circle>
					{/each}
				</g>
				{#each donut.donutLeaders as l, i (i)}
					<polyline points={l.points} fill="none" stroke={l.color} stroke-width="1" opacity="0.6"
					></polyline>
				{/each}
			</svg>
			{#each donut.donutLeaders as l, i (i)}
				<div
					class="leader-label"
					style="left:{l.lp}%;top:{l.tp}%;transform:{l.tf};text-align:{l.align};"
				>
					<span class="leader-name">{l.label}</span>
					<span class="leader-pct" style="color:{l.color};">{l.pct}</span>
				</div>
			{/each}
		</div>
	</div>

	<div class="controls-group">
		<!-- zoom -->
		<div class="glass zoom-control">
			<button class="zoom-btn" aria-label="Zoom in" onclick={() => dash.zoomBy(0.5)}>+</button>
			<button class="zoom-btn" aria-label="Zoom out" onclick={() => dash.zoomBy(-0.5)}>−</button>
		</div>

		<!-- mode toggle -->
		<div class="glass mode-toggle">
			{#each tabs as t (t.id)}
				<button
					class="mode-btn"
					style="background:{t.active ? 'var(--gold)' : 'transparent'};color:{t.active
						? '#0e1220'
						: 'var(--txd)'};"
					onclick={() => dash.setMapMode(t.id)}
				>
					{t.label}
				</button>
			{/each}
		</div>
	</div>
</div>

<style>
	.rail {
		position: absolute;
		top: 16px;
		right: 16px;
		bottom: 14px;
		width: 240px;
		z-index: 520;
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		align-items: flex-end;
		gap: 12px;
		pointer-events: none;
	}
	.card,
	.donut-card,
	.zoom-control,
	.mode-toggle {
		pointer-events: auto;
	}
	.card {
		width: 100%;
		border-radius: 18px;
		padding: 14px 16px;
	}
	.entity-name {
		font-family: var(--font-display);
		font-weight: 600;
		font-size: 18px;
		color: var(--tx);
		margin: 0 0 9px;
		line-height: 1.15;
	}
	.cat-row {
		display: flex;
		align-items: center;
		gap: 8px;
		margin-bottom: 10px;
	}
	.cat-row .swatch {
		width: 10px;
		height: 10px;
		border-radius: 3px;
	}
	.cat-label {
		font-size: 12.5px;
		color: var(--txd);
	}
	.index-row,
	.sites-row {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
	}
	.index-row {
		margin-bottom: 6px;
	}
	.sites-row {
		margin-top: 10px;
	}
	.index-label {
		font-size: 11px;
		color: var(--txf);
	}
	.index-value {
		font-family: var(--font-mono);
		font-size: 13px;
		color: var(--tx);
	}
	.sites-value {
		font-family: var(--font-display);
		font-weight: 600;
		font-size: 15px;
		color: var(--tx);
		font-variant-numeric: tabular-nums;
	}
	.index-track {
		height: 7px;
		border-radius: 999px;
		background: rgba(127, 127, 127, 0.2);
		overflow: hidden;
	}
	.index-fill {
		height: 100%;
		background: linear-gradient(90deg, var(--gold), #f79d5c);
		border-radius: 999px;
		transition: width 0.35s ease;
	}

	.donut-card {
		width: 100%;
		border-radius: 18px;
		padding: 9px 12px 5px;
	}
	.donut-wrap {
		position: relative;
	}
	.donut-svg {
		width: 100%;
		height: auto;
		display: block;
	}
	.donut-seg {
		transition:
			stroke-dasharray 0.5s ease,
			stroke-dashoffset 0.5s ease;
	}
	.leader-label {
		position: absolute;
		line-height: 1;
		white-space: nowrap;
		pointer-events: none;
	}
	.leader-name {
		font-size: 8px;
		font-weight: 500;
		color: var(--tx);
	}
	.leader-pct {
		font-size: 8px;
		font-weight: 700;
		margin-left: 2px;
	}

	.controls-group {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 10px;
	}
	.zoom-control {
		display: flex;
		flex-direction: column;
		border-radius: 12px;
		overflow: hidden;
	}
	.zoom-btn {
		width: 38px;
		height: 36px;
		border: none;
		background: transparent;
		cursor: pointer;
		color: var(--tx);
		font-size: 20px;
		line-height: 1;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.zoom-btn:first-child {
		border-bottom: 1px solid var(--glassbd);
	}
	.zoom-btn:hover {
		background: rgba(127, 127, 127, 0.16);
	}
	.mode-toggle {
		display: inline-flex;
		border-radius: 999px;
		padding: 3px;
	}
	.mode-btn {
		border: none;
		border-radius: 999px;
		padding: 7px 16px;
		cursor: pointer;
		font-size: 12.5px;
		font-weight: 600;
		transition: background 0.2s;
	}

	@media (max-width: 720px) {
		.rail {
			display: none;
		}
	}
</style>