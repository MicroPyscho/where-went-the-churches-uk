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
		bottom: 16px;
		left: 16px;
		z-index: 420;
		border-radius: 12px;
		padding: 10px 14px;
	}
	.items {
		display: flex;
		flex-wrap: wrap;
		gap: 7px 14px;
		max-width: 300px;
	}
	.item {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		font-size: 11px;
		color: var(--txd);
	}
	.chip {
		width: 13px;
		height: 8px;
		border-radius: 2px;
	}

	@media (max-width: 720px) {
		.legend {
			display: none;
		}
	}
</style>
