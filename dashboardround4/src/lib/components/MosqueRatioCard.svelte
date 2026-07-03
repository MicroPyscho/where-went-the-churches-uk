<script lang="ts">
	import { mosqueRatio } from '$lib/viewmodel';

	let m = $derived(mosqueRatio());
</script>

<div class="glass card">
	<p class="kicker">Residential : Mosque</p>
	{#if m.ratio !== null}
		<div class="ratio-row">
			<span class="ratio-value">{m.ratio}</span>
			<span class="ratio-sep">:</span>
			<span class="ratio-value ratio-one">1</span>
		</div>
		<p class="caption">
			Residential conversions remain <strong>{m.ratio}×</strong> more common than mosque conversions
			in {m.scope}.
			{#if m.lowSample}
				<span class="caveat"
					>Based on {m.mosque} recorded mosque conversion{m.mosque === 1 ? '' : 's'} here —
					indicative, not precise.</span
				>
			{/if}
		</p>
	{:else}
		<div class="ratio-row">
			<span class="ratio-value">{m.residential.toLocaleString()}</span>
			<span class="ratio-sep">:</span>
			<span class="ratio-value ratio-one">0</span>
		</div>
		<p class="caption">
			No mosque conversions recorded in {m.scope} — {m.residential.toLocaleString()} residential conversions
			by comparison.
		</p>
	{/if}
</div>

<style>
	.card {
		width: 100%;
		border-radius: 20px;
		padding: 22px 26px 20px;
	}
	.ratio-row {
		display: flex;
		align-items: baseline;
		gap: 10px;
		margin: 2px 0 10px;
	}
	.ratio-value {
		font-family: var(--font-display);
		font-weight: 700;
		font-size: 40px;
		color: var(--gold);
		letter-spacing: -0.01em;
	}
	.ratio-one {
		color: var(--tx);
	}
	.ratio-sep {
		font-family: var(--font-display);
		font-weight: 600;
		font-size: 28px;
		color: var(--txf);
	}
	.caption {
		font-size: 14px;
		line-height: 1.5;
		color: var(--txd);
		margin: 0;
	}
	.caption strong {
		color: var(--tx);
	}
	.caveat {
		display: block;
		margin-top: 6px;
		font-size: 12px;
		color: var(--txf);
	}

	@media (max-width: 1080px) {
		.card {
			border-radius: 16px;
			padding: 18px 20px 16px;
		}
		.ratio-value {
			font-size: 32px;
		}
		.ratio-sep {
			font-size: 22px;
		}
		.caption {
			font-size: 13px;
		}
	}
</style>
