<script lang="ts">
	import '$lib/design/tokens.css';
	import '$lib/design/dashboard.css';
	import 'leaflet/dist/leaflet.css';
	import { dash } from '$lib/state.svelte';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
	<meta name="theme-color" content="#000000" />
	<title>Nave — Where Went the Churches?</title>
	<meta
		name="description"
		content="A live interactive atlas of former UK churches and what they became."
	/>
	<link rel="preconnect" href="https://fonts.googleapis.com" />
	<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="" />
	<link
		href="https://fonts.googleapis.com/css2?family=Familjen+Grotesk:wght@400;500;600;700&display=swap"
		rel="stylesheet"
	/>
</svelte:head>

<div class="tc-root" data-tc-theme={dash.theme}>
	{@render children()}
</div>