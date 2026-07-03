<script lang="ts">
	import { resolveSelection, bars } from '$lib/viewmodel';
	import { catLabel } from '$lib/design/categories';

	let sel = $derived(resolveSelection());
	let topShare = $derived(sel.n ? Math.round((sel.mix ? Math.max(...sel.mix) : 0) / sel.n * 100) : 0);
	let barData = $derived(bars(sel));
	let metricValue = $derived((sel.n || 0).toLocaleString());
	let metricDelta = $derived(
		`${topShare}% ${sel.cat === 'residential' ? 'homes' : catLabel(sel.cat).split(' ')[0].toLowerCase()}`
	);
	let metricLabel = $derived(`Former churches · ${sel.name}`);
</script>

<div class="glass metric-card">
	<div class="metric-top">
		<span class="metric-value">{metricValue}</span>
		<span class="metric-delta">{metricDelta}</span>
	</div>
	<p class="metric-label">{metricLabel}</p>
	<div class="bars">
		{#each barData.bars as b, i (i)}
			<span class="bar" style="height:{b.h};"></span>
		{/each}
	</div>
	<div class="bar-caption"><span>{barData.caption}</span></div>
</div>

<style>
	.metric-card {
		position: absolute;
		top: 300px;
		left: 28px;
		z-index: 420;
		width: 25%;
		min-width: 300px;
		max-width: 480px;
		border-radius: 20px;
		padding: 26px 28px 22px;
	}
	.metric-top {
		display: flex;
		align-items: baseline;
		gap: 12px;
	}
	.metric-value {
		font-family: var(--font-display);
		font-weight: 700;
		font-size: 42px;
		color: var(--tx);
		letter-spacing: -0.01em;
	}
	.metric-delta {
		font-size: 15px;
		font-weight: 600;
		color: #fff;
		background: #717ec3;
		border-radius: 8px;
		padding: 4px 11px;
	}
	.metric-label {
		font-size: 15px;
		color: var(--txd);
		margin: 8px 0 0;
	}
	.bars {
		display: flex;
		align-items: flex-end;
		gap: 7px;
		height: 100px;
		margin-top: 20px;
	}
	.bar {
		flex: 1;
		border-radius: 4px 4px 0 0;
		background: linear-gradient(180deg, var(--gold), rgba(238, 132, 52, 0.25));
	}
	.bar-caption {
		display: flex;
		justify-content: center;
		font-size: 13px;
		color: var(--txf);
		margin-top: 12px;
	}

	@media (max-width: 1080px) {
		.metric-card {
			position: static;
			width: 100%;
			min-width: 0;
			max-width: none;
			border-radius: 16px;
			padding: 18px 20px 16px;
		}
		.metric-value {
			font-size: 30px;
		}
		.metric-delta {
			font-size: 12px;
			padding: 3px 8px;
		}
		.metric-label {
			font-size: 12.5px;
		}
		.bars {
			height: 64px;
			margin-top: 14px;
		}
		.bar-caption {
			font-size: 11px;
		}
	}
</style>
