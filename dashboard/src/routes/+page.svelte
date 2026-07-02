<script lang="ts">
	import { dash } from '$lib/state.svelte';
	import Header from '$lib/components/Header.svelte';
	import NaveMap from '$lib/components/NaveMap.svelte';
	import SearchPanel from '$lib/components/SearchPanel.svelte';
	import MastheadCard from '$lib/components/MastheadCard.svelte';
	import RightRail from '$lib/components/RightRail.svelte';
	import LegendPanel from '$lib/components/LegendPanel.svelte';
	import MobileBar from '$lib/components/MobileBar.svelte';

	let dark = $derived(dash.theme === 'dark');
	let posterBg = $derived(dark ? '#0d1017' : '#e9edf0');
	let posterScrim = $derived(
		dark
			? 'linear-gradient(180deg,rgba(6,8,14,.4) 0%,rgba(6,8,14,0) 26%,rgba(6,8,14,0) 50%,rgba(6,8,14,.6) 100%)'
			: 'linear-gradient(180deg,rgba(255,255,255,.4) 0%,rgba(255,255,255,0) 26%,rgba(255,255,255,0) 50%,rgba(255,255,255,.55) 100%)'
	);
	let posterLine = $derived(dark ? 'rgba(229,229,235,.16)' : 'rgba(40,50,60,.18)');
	let posterColor = $derived(dark ? '#f79d5c' : '#a8410f');
</script>

<Header />

<main class="dashboard" style="background:{posterBg};--poster-color:{posterColor};">
	<NaveMap />

	<div class="scrim" style="background:{posterScrim};"></div>
	<div class="frame" style="border-color:{posterLine};"></div>

	<span class="north-sea" style="color:{posterColor};">North Sea</span>

	<SearchPanel />
	<MastheadCard />
	<RightRail />
	<LegendPanel />
	<MobileBar />

	<span class="attribution" style="color:{posterColor};">© OpenStreetMap contributors</span>
</main>

<style>
	.dashboard {
		position: relative;
		height: calc(100dvh - 56px);
		min-height: 480px;
		overflow: hidden;
	}
	.scrim {
		position: absolute;
		inset: 0;
		pointer-events: none;
		z-index: 380;
	}
	.frame {
		position: absolute;
		inset: 10px;
		pointer-events: none;
		z-index: 381;
		border: 1px solid;
		border-radius: 8px;
	}
	.north-sea {
		position: absolute;
		top: 30%;
		right: 11%;
		z-index: 386;
		pointer-events: none;
		font-family: var(--font-display);
		font-size: clamp(11px, 1.5vw, 17px);
		font-weight: 500;
		letter-spacing: 0.42em;
		text-transform: uppercase;
		opacity: 0.5;
		transform: rotate(-6deg);
		text-indent: 0.42em;
	}
	.attribution {
		position: absolute;
		left: 0;
		right: 0;
		bottom: 6px;
		text-align: center;
		z-index: 420;
		font-family: var(--font-mono);
		font-size: 10.5px;
		letter-spacing: 0.04em;
		opacity: 0.55;
	}

	@media (max-width: 720px) {
		.north-sea {
			display: none;
		}
		.attribution {
			display: none;
		}
	}
</style>
