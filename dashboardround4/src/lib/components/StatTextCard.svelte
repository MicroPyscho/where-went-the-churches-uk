<script lang="ts">
	import { resolveSelection, hoverInfo } from '$lib/viewmodel';

	let sel = $derived(resolveSelection());
	let hover = $derived(hoverInfo(sel));
</script>

<div class="glass card">
	<p class="kicker">{hover.kicker}</p>
	<p class="entity-name">{hover.name}</p>
	<div class="sites-row">
		<span class="index-label">Total entries</span>
		<span class="sites-value">{hover.sites}</span>
	</div>

	<p class="breakdown-title">Churches converted to</p>
	<ul class="breakdown-list">
		{#each hover.breakdown as b (b.label)}
			<li class="breakdown-row">
				<span class="swatch" style="background:{b.color};"></span>
				<span class="breakdown-label">{b.label}</span>
				<span class="breakdown-count">{b.count}</span>
				<span class="breakdown-pct">{b.pct}</span>
			</li>
		{/each}
	</ul>
</div>

<style>
	.card {
		position: absolute;
		top: 24px;
		right: 24px;
		z-index: 420;
		width: 30%;
		min-width: 440px;
		max-width: 560px;
		border-radius: 20px;
		padding: 24px 26px;
	}
	.entity-name {
		font-family: var(--font-display);
		font-weight: 600;
		font-size: 30px;
		color: var(--tx);
		margin: 0 0 14px;
		line-height: 1.15;
	}
	.sites-row {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		padding-bottom: 14px;
		border-bottom: 1px solid var(--bd);
	}
	.index-label {
		font-size: 14px;
		color: var(--txf);
	}
	.sites-value {
		font-family: var(--font-display);
		font-weight: 600;
		font-size: 22px;
		color: var(--tx);
		font-variant-numeric: tabular-nums;
	}
	.breakdown-title {
		font-family: var(--font-display);
		font-size: 11px;
		letter-spacing: 0.18em;
		text-transform: uppercase;
		color: var(--txf);
		margin: 16px 0 10px;
	}
	.breakdown-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 10px;
	}
	.breakdown-row {
		display: flex;
		align-items: center;
		gap: 10px;
		font-size: 15px;
	}
	.breakdown-row .swatch {
		width: 10px;
		height: 10px;
		border-radius: 3px;
		flex-shrink: 0;
	}
	.breakdown-label {
		flex: 1;
		min-width: 0;
		color: var(--txd);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.breakdown-count {
		font-family: var(--font-mono);
		color: var(--tx);
		font-variant-numeric: tabular-nums;
	}
	.breakdown-pct {
		font-family: var(--font-mono);
		color: var(--txf);
		font-size: 12.5px;
		width: 3.5ch;
		text-align: right;
	}

	@media (max-width: 1080px) {
		.card {
			position: static;
			width: 100%;
			min-width: 0;
			max-width: none;
			border-radius: 16px;
			padding: 18px 20px;
		}
		.entity-name {
			font-size: 22px;
			margin: 0 0 10px;
		}
		.sites-row {
			padding-bottom: 10px;
		}
		.breakdown-title {
			margin: 12px 0 8px;
		}
		.breakdown-row {
			font-size: 13.5px;
		}
	}
</style>
