<script lang="ts">
	import { dash } from '$lib/state.svelte';
	import { searchCountries, subPanel, searchResults } from '$lib/viewmodel';

	let countries = $derived(searchCountries());
	let sub = $derived(subPanel());
	let results = $derived(searchResults());
	let q = $derived(dash.searchQuery.trim());
	let isMobile = $state(false);
	$effect(() => {
		const mq = window.matchMedia('(max-width: 720px)');
		const update = () => (isMobile = mq.matches);
		update();
		mq.addEventListener('change', update);
		return () => mq.removeEventListener('change', update);
	});
	let showCountries = $derived(dash.searchOpen && !q && !(isMobile && dash.openCountry));
	let showResults = $derived(dash.searchOpen && !!q);
	let noResults = $derived(!!q && results.length === 0);
	let selectionActive = $derived(dash.selection.level !== 'uk');
	let selectionLabel = $derived(
		dash.selection.level === 'city' ? (dash.selection.data?.name ?? '') : (dash.selection.key ?? '')
	);

	function enter() {
		dash.openSearch();
	}
	function leave() {
		dash.closeSearch();
	}
</script>

<div class="search-wrap" onmouseenter={enter} onmouseleave={leave} role="search">
	{#if dash.openCountry && sub.items.length}
		<div class="glass sub-panel">
			<div class="sub-panel-head">
				{#if isMobile}
					<button class="btn-reset back-btn" onclick={() => (dash.openCountry = null)}
						>‹ Countries</button
					>
				{/if}
				<p class="kicker" style="margin:2px 10px 8px;">{sub.title} · regions</p>
			</div>
			{#each sub.items as it (it.label)}
				<button class="row-btn" onclick={it.go}>
					<span class="swatch" style="background:{it.color};"></span>
					<span style="flex:1;min-width:0;">
						<span class="row-label">{it.label}</span>
						<span class="row-sub">{it.sub}</span>
					</span>
				</button>
			{/each}
		</div>
	{/if}

	<div class="glass search-pill">
		<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--txf)" stroke-width="2">
			<circle cx="11" cy="11" r="7"></circle>
			<line x1="21" y1="21" x2="16.65" y2="16.65"></line>
		</svg>
		<input
			value={dash.searchQuery}
			oninput={(e) => dash.onQuery((e.target as HTMLInputElement).value)}
			onfocus={enter}
			placeholder="Search a city or region…"
			class="search-input"
		/>
		{#if selectionActive}
			<button class="btn-reset clear-pill" onclick={() => dash.clearSelection()}
				>{selectionLabel} ✕</button
			>
		{/if}
	</div>

	{#if showCountries}
		<div class="glass dropdown">
			<p class="kicker" style="margin:2px 10px 8px;">Browse by country</p>
			{#each countries as c (c.name)}
				<button
					class="row-btn"
					style="background:{c.active ? 'rgba(127,127,127,.14)' : 'transparent'};"
					onmouseenter={isMobile ? undefined : c.hover}
					onclick={c.go}
				>
					<span style="flex:1;font-size:14px;font-weight:500;">{c.name}</span>
					<span style="font-size:11px;color:var(--txf);font-variant-numeric:tabular-nums;"
						>{c.count}</span
					>
					<span style="font-size:13px;color:var(--gold);width:12px;text-align:center;">{c.chev}</span>
				</button>
			{/each}
		</div>
	{/if}

	{#if showResults}
		<div class="glass dropdown">
			{#each results as r (r.label + r.sub)}
				<button class="row-btn" onclick={r.go}>
					<span class="swatch" style="background:{r.color};"></span>
					<span style="flex:1;min-width:0;">
						<span class="row-label">{r.label}</span>
						<span class="row-sub">{r.sub}</span>
					</span>
				</button>
			{/each}
			{#if noResults}
				<p class="no-results">No match — try a city or region name.</p>
			{/if}
		</div>
	{/if}
</div>

<style>
	.search-wrap {
		position: absolute;
		top: 16px;
		left: 50%;
		transform: translateX(-50%);
		z-index: 600;
		width: 330px;
		max-width: calc(100% - 28px);
	}
	.sub-panel {
		position: absolute;
		top: 0;
		right: calc(100% + 12px);
		width: 238px;
		border-radius: 16px;
		padding: 10px 8px;
		max-height: 360px;
		overflow: auto;
	}
	.search-pill {
		display: flex;
		align-items: center;
		gap: 9px;
		border-radius: 999px;
		padding: 9px 15px;
	}
	.search-input {
		flex: 1;
		min-width: 0;
		background: none;
		border: none;
		outline: none;
		color: var(--tx);
		font-size: 13.5px;
		font-family: var(--font-sans);
	}
	.clear-pill {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		background: var(--gold);
		color: #0d1017;
		border-radius: 999px;
		padding: 4px 10px;
		font-size: 11px;
		font-weight: 600;
		white-space: nowrap;
		flex-shrink: 0;
	}
	.dropdown {
		margin-top: 8px;
		border-radius: 16px;
		padding: 8px;
		max-height: 320px;
		overflow: auto;
	}
	.sub-panel-head {
		display: flex;
		align-items: center;
		gap: 8px;
	}
	.back-btn {
		font-size: 11px;
		font-weight: 600;
		color: var(--gold);
		padding: 4px 8px 4px 10px;
		white-space: nowrap;
	}
	.row-label {
		display: block;
		font-size: 13px;
		font-weight: 500;
		line-height: 1.15;
	}
	.row-sub {
		display: block;
		font-size: 10.5px;
		color: var(--txf);
	}
	.no-results {
		font-size: 12px;
		color: var(--txf);
		padding: 10px;
		margin: 0;
		text-align: center;
	}

	@media (max-width: 720px) {
		.search-wrap {
			top: 12px;
			width: 100%;
		}
		.sub-panel {
			right: auto;
			left: 0;
			width: 100%;
			top: calc(100% + 8px);
			max-height: min(360px, calc(100dvh - 220px));
		}
		.sub-panel.glass,
		.dropdown.glass {
			background: var(--bg2);
		}
	}
</style>
