<script lang="ts">
	import { page } from '$app/state';
	import { dash } from '$lib/state.svelte';

	let theme = $derived(dash.theme);
	let themeIcon = $derived(theme === 'dark' ? '☀' : '☾');
	let onSignup = $derived(page.url.pathname.startsWith('/signup'));
</script>

<header class="header">
	<div class="header-inner">
		<div class="brand">
			<span aria-label="nave" role="img" class="brand-mark">
				<svg viewBox="0 0 660.23 154.29" xmlns="http://www.w3.org/2000/svg">
					<path
						d="M101.23,2.59c15.55,0,30.43,5.15,40.24,13.62,10.48,9.68,14.2,21.19,14.2,46v88.51h-51.39l-2.23-88.21c0-13.62-11.47-21.79-24.65-21.79s-24.99,10.78-24.99,24.4v85.6H1V52.74C1,27.15,22.25,2.54,50.84,3.06c16.23.29,42.98-.47,50.38-.47Z"
						fill="currentColor"
						stroke="currentColor"
						stroke-miterlimit="10"
						stroke-width="2"
					></path>
					<path
						d="M271.03,72.88l-4.3,3.99-4.22-9.31c-2.91-4.9-4.25-5.4-4.8-5.89-2.03-1.81-3.85-3.52-7.97-4.48l-11.44-1.14,4.78-4.2,5.44.21c1.58.06,3.15.28,4.67.7,2.85.79,4.12,1.51,5.94,2.75,2.68,1.83,3.96,3.21,6.17,5.79,1.63,1.91,3.06,4.92,4.22,7.15l1.52,4.43Z"
						fill="currentColor"
					></path>
					<path
						d="M265.4,56.33l-3.25,1c-2.44.75-3.58,2.3-5.76,3.63-2.02,1.23-4.52,7.02-4.61,7.15l-6.42-4.2s2.65-4.64,4.28-6.12c2.41-2.18,5.16-3.93,8.19-5.47,2.24-1.14,7.56,4,7.56,4Z"
						fill="currentColor"
					></path>
					<path
						d="M236.42,2.59c-42.07,0-72.64,32.69-72.64,77.48s28.09,70.65,68.04,70.65h94.18V1.02s-71.73,1.57-89.58,1.57ZM243.1,110.29c-18.76,0-35.29-9.64-35.29-31.13s13.26-33.44,35.59-33.44c19.98,0,34.2,10.44,34.2,32.84,0,21.18-15.43,31.73-34.5,31.73ZM275.32,47.42c-5.47,0-9.92-4.18-9.92-9.32s4.45-9.33,9.92-9.33,9.93,4.18,9.93,9.33-4.45,9.32-9.93,9.32Z"
						fill="currentColor"
						stroke="currentColor"
						stroke-miterlimit="10"
						stroke-width="2"
					></path>
					<path
						d="M533.33,4.72c.25-.84-104.39,122.38-112.3,129.21-16.19,13.98-23.41,19.01-41.02,19.37h-10.18c-19.75,0-35.75-16.02-35.72-35.77l.15-114.36h55.12l-.06,78.09c0,5.36,6.46,12.58,16,1.23L471.87,4.72h61.46Z"
						fill="currentColor"
						stroke="currentColor"
						stroke-miterlimit="10"
						stroke-width="2"
					></path>
					<path
						d="M552,89.07c3.33,15.74,14.67,20.14,31.31,20.14,12.41,0,20.16-4.95,25-14.94l49.97.72c-.56,9.04-4.84,26.08-26.16,41.04-5.51,3.87-19.82,16.27-49.97,16.27-45.7,0-83.68-29.33-83.68-73.82S536.36,2.72,581.75,2.72s77.48,32.78,77.48,80.59v5.75h-107.23ZM609.32,61.55c-3.03-14.53-10.92-19.7-27.26-19.7s-25.33,5.17-28.36,19.7h55.62Z"
						fill="currentColor"
						stroke="currentColor"
						stroke-miterlimit="10"
						stroke-width="2"
					></path>
				</svg>
			</span>
			<span class="badge">Live atlas · UK</span>
		</div>
		<nav class="nav">
			{#if onSignup}
				<a href="/" class="signup-link">← Back to dashboard</a>
			{:else}
				<a href="/signup" class="signup-link">Sign up</a>
			{/if}
			<button
				class="icon-btn"
				onclick={() => dash.toggleTheme()}
				title="Toggle appearance"
				aria-label="Toggle appearance"
			>
				{themeIcon}
			</button>
		</nav>
	</div>
</header>

<style>
	.header {
		position: sticky;
		top: 0;
		z-index: 1200;
		backdrop-filter: saturate(150%) blur(18px);
		-webkit-backdrop-filter: saturate(150%) blur(18px);
		background: var(--head);
		border-bottom: 1px solid var(--bdg);
	}
	.header-inner {
		max-width: 1440px;
		margin: 0 auto;
		padding: 0 clamp(14px, 4vw, 32px);
		height: 56px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
	}
	.brand {
		display: flex;
		align-items: center;
		gap: 12px;
		min-width: 0;
	}
	.brand-mark {
		display: inline-flex;
		color: var(--tx);
		flex-shrink: 0;
	}
	.brand-mark svg {
		height: 17px;
		width: auto;
		display: block;
	}
	.badge {
		font-size: 11px;
		letter-spacing: 0.04em;
		color: var(--txf);
		padding: 3px 9px;
		border: 1px solid var(--bd);
		border-radius: 999px;
		white-space: nowrap;
	}
	.nav {
		display: flex;
		align-items: center;
		gap: clamp(10px, 2vw, 20px);
		flex-shrink: 0;
	}
	.signup-link {
		text-decoration: none;
		color: var(--txd);
		font-size: 13px;
		font-weight: 500;
		white-space: nowrap;
	}
	.signup-link:hover {
		color: var(--tx);
	}
	@media (max-width: 480px) {
		.badge {
			display: none;
		}
	}
</style>
