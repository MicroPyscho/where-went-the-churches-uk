<script lang="ts">
	import { dash } from '$lib/state.svelte';
	import Header from '$lib/components/Header.svelte';
	import NaveMap from '$lib/components/NaveMap.svelte';
	import SearchPanel from '$lib/components/SearchPanel.svelte';
	import MapTitle from '$lib/components/MapTitle.svelte';
	import ModeZoomControls from '$lib/components/ModeZoomControls.svelte';
	import MetricBarsCard from '$lib/components/MetricBarsCard.svelte';
	import DonutCard from '$lib/components/DonutCard.svelte';
	import MosqueRatioCard from '$lib/components/MosqueRatioCard.svelte';
	import LegendPanel from '$lib/components/LegendPanel.svelte';
	import StatTextCard from '$lib/components/StatTextCard.svelte';
	import DatasetLinkCard from '$lib/components/DatasetLinkCard.svelte';
	import Footer from '$lib/components/Footer.svelte';

	let dark = $derived(dash.theme === 'dark');
	let posterBg = $derived(dark ? '#0d1017' : '#e9edf0');
	let posterScrim = $derived(
		dark
			? 'linear-gradient(180deg,rgba(6,8,14,.4) 0%,rgba(6,8,14,0) 26%,rgba(6,8,14,0) 50%,rgba(6,8,14,.6) 100%)'
			: 'linear-gradient(180deg,rgba(255,255,255,.4) 0%,rgba(255,255,255,0) 26%,rgba(255,255,255,0) 50%,rgba(255,255,255,.55) 100%)'
	);
	let posterLine = $derived(dark ? 'rgba(229,229,235,.16)' : 'rgba(40,50,60,.18)');
	let posterColor = $derived(dark ? '#f79d5c' : '#a8410f');
	let densityMode = $derived(dash.mapMode === 'density');
</script>

<Header />

<!--
  Three layouts share this one DOM order (which is also the mobile scroll
  order — keep it in this sequence):
    Desktop (>1080px): `.dashboard` is a fixed-height poster; every card
      below `.map-frame` is position:absolute, overlaid on the map.
    Tablet (721-1080px): `.dashboard` becomes a 33/66 grid — cards stack in
      the left column, `.map-frame` fills the right column.
    Mobile (<=720px): `.dashboard` is a normal flowing column; `.map-frame`
      is a fixed-height block up top, cards stack full-width below it.
  Each card switches its own position:absolute -> static at <=1080px (see
  the component's own style block) — this file only owns the container.
-->
<main class="dashboard" style="--poster-color:{posterColor};">
	<div class="map-frame" style="background:{posterBg};">
		<NaveMap />
		<div class="scrim" style="background:{posterScrim};"></div>
		<div class="frame" style="border-color:{posterLine};"></div>
		<span class="north-sea" style="color:{posterColor};">North Sea</span>

		<MapTitle />
		<SearchPanel />
		<ModeZoomControls />

		<span class="attribution" style="color:{posterColor};">© OpenStreetMap contributors</span>
	</div>

	<!-- side-stack is `display:contents` outside tablet width, so on desktop
	     and mobile its children behave exactly as if they were direct
	     children of .dashboard (unaffected by this wrapper). At tablet width
	     it becomes the SINGLE grid item in column 1 — critical because
	     .map-frame spans grid-row:1/-1: if the six cards below were each
	     their own auto-placed row (as before), the grid would stretch those
	     implicit rows to match the map's tall fixed height, leaving huge
	     blank gaps under every short card. One flex container avoids that. -->
	<div class="side-stack">
		<div class="metrics-slot">
			<MetricBarsCard />
		</div>

		<!-- grouped so the donut's aspect-ratio-driven height (it grows taller
		     as its column widens on large monitors) can never push into the
		     mosque-ratio card below it — flexbox gap absorbs that automatically,
		     where two independently-positioned cards previously couldn't. -->
		<div class="donut-mosque-stack" class:density-mode={densityMode}>
			<DonutCard />
			<MosqueRatioCard />
		</div>

		<!-- on mobile, density mode moves this ahead of the donut+mosque pair
		     (see the max-width:720px `order` rules below) — category-based
		     breakdowns matter less once the map itself is showing density. -->
		<div class="legend-slot" class:density-mode={densityMode}>
			<LegendPanel />
		</div>
		<div class="stat-slot">
			<StatTextCard />
		</div>
		<div class="dataset-slot">
			<DatasetLinkCard />
		</div>
		<div class="footer-slot">
			<Footer />
		</div>
	</div>
</main>

<style>
	.dashboard {
		position: relative;
		/* On tall viewports the poster simply fills the screen, same as
		   before. On common laptop/desktop heights (~800-950px) the cards
		   genuinely need more vertical room than the viewport gives, so the
		   canvas — and the map filling it — grows to a comfortable minimum
		   and the page scrolls, rather than clipping or overlapping cards. */
		height: max(calc(100dvh - var(--header-h)), 1400px);
		min-height: 480px;
	}
	.map-frame {
		position: absolute;
		inset: 0;
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
		top: 18%;
		right: 34%;
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

	/* outside tablet width this wrapper is invisible to layout — its
	   children act as direct children of .dashboard, same as before it
	   existed. */
	.side-stack {
		display: contents;
	}

	/* desktop: the donut+mosque pair sits below StatTextCard (top:24, and
	   at most ~380px tall with a full 5-row breakdown) — 420px comfortably
	   clears it regardless of how many breakdown rows the current
	   selection has. */
	.donut-mosque-stack {
		position: absolute;
		top: 420px;
		right: 24px;
		z-index: 420;
		width: 30%;
		min-width: 440px;
		max-width: 560px;
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	/* ── tablet: 33% sidebar (all cards, stacked, equal gaps) + 66% map ── */
	@media (min-width: 721px) and (max-width: 1080px) {
		.dashboard {
			height: auto;
			min-height: 0;
			display: grid;
			grid-template-columns: 33% 1fr;
			align-items: start;
			gap: 20px;
			padding: 20px;
		}
		.side-stack {
			display: flex;
			flex-direction: column;
			gap: 20px;
			grid-column: 1;
			grid-row: 1;
			min-width: 0;
		}
		.map-frame {
			position: relative;
			inset: auto;
			grid-column: 2;
			grid-row: 1;
			height: calc(100dvh - var(--header-h) - 40px);
			min-height: 460px;
			border-radius: 16px;
		}
		.donut-mosque-stack {
			position: static;
			width: 100%;
			min-width: 0;
			max-width: none;
		}
		.north-sea {
			display: none;
		}
	}

	@media (max-width: 720px) {
		.dashboard {
			height: auto;
			min-height: 0;
			padding: 0 14px 28px;
			display: flex;
			flex-direction: column;
			gap: 16px;
		}
		.map-frame {
			position: relative;
			inset: auto;
			height: 62vh;
			min-height: 380px;
			margin: 14px -14px 0;
			border-radius: 0 0 20px 20px;
		}
		.donut-mosque-stack {
			position: static;
			width: 100%;
			min-width: 0;
			max-width: none;
		}
		/* fixed sequence in category mode, matching original DOM order;
		   density mode reorders only the legend ("Site density") ahead of
		   the donut+mosque pair — everything else keeps its place. */
		.metrics-slot {
			order: 1;
		}
		.donut-mosque-stack {
			order: 2;
		}
		.legend-slot {
			order: 3;
		}
		.stat-slot {
			order: 4;
		}
		.dataset-slot {
			order: 5;
		}
		.footer-slot {
			order: 6;
		}
		.donut-mosque-stack.density-mode {
			order: 3;
		}
		.legend-slot.density-mode {
			order: 2;
		}
		.north-sea {
			display: none;
		}
		.attribution {
			display: none;
		}
	}
</style>
