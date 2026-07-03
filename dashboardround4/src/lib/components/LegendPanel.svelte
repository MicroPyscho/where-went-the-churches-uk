<script lang="ts">
	import { legend, legendTitle } from '$lib/viewmodel';

	let items = $derived(legend());
	let title = $derived(legendTitle());
</script>

<div class="glass legend">
	<p class="kicker" style="margin:0 0 8px;">{title}</p>
	<div class="items">
		{#each items as g, i (i)}
			<span class="item">
				<span class="chip" style="background:{g.color};"></span>{g.label}
			</span>
		{/each}
	</div>
</div>

<style>
	.legend {
		position: absolute;
		bottom: 24px;
		left: 28px;
		z-index: 420;
		border-radius: 16px;
		padding: 16px 20px;
		max-width: min(25%, 420px);
	}
	.items {
		display: flex;
		flex-wrap: wrap;
		gap: 10px 20px;
	}
	.item {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		font-size: 15px;
		color: var(--txd);
	}
	.chip {
		width: 17px;
		height: 11px;
		border-radius: 3px;
	}

	@media (max-width: 1080px) {
		.legend {
			position: static;
			width: 100%;
			max-width: none;
			border-radius: 16px;
			padding: 18px 20px;
		}
		.item {
			font-size: 14px;
		}
	}
</style>
