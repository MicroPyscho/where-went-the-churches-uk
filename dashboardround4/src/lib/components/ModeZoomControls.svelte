<script lang="ts">
	import { dash } from '$lib/state.svelte';
	import { mapTabs } from '$lib/viewmodel';

	let tabs = $derived(mapTabs());
</script>

<div class="controls-group">
	<div class="glass zoom-control">
		<button class="zoom-btn" aria-label="Zoom in" onclick={() => dash.zoomBy(0.5)}>+</button>
		<button class="zoom-btn" aria-label="Zoom out" onclick={() => dash.zoomBy(-0.5)}>−</button>
	</div>

	<div class="glass mode-toggle">
		{#each tabs as t (t.id)}
			<button
				class="mode-btn"
				style="background:{t.active ? 'var(--gold)' : 'transparent'};color:{t.active
					? '#0e1220'
					: 'var(--txd)'};"
				onclick={() => dash.setMapMode(t.id)}
			>
				{t.label}
			</button>
		{/each}
	</div>
</div>

<style>
	.controls-group {
		position: absolute;
		bottom: 20px;
		right: 24px;
		z-index: 520;
		display: flex;
		align-items: center;
		gap: 14px;
		pointer-events: auto;
	}
	.zoom-control {
		display: flex;
		flex-direction: column;
		border-radius: 14px;
		overflow: hidden;
	}
	.zoom-btn {
		width: 54px;
		height: 50px;
		border: none;
		background: transparent;
		cursor: pointer;
		color: var(--tx);
		font-size: 28px;
		line-height: 1;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.zoom-btn:first-child {
		border-bottom: 1px solid var(--glassbd);
	}
	.zoom-btn:hover {
		background: rgba(127, 127, 127, 0.16);
	}
	.mode-toggle {
		display: inline-flex;
		border-radius: 999px;
		padding: 4px;
	}
	.mode-btn {
		border: none;
		border-radius: 999px;
		padding: 11px 22px;
		cursor: pointer;
		font-size: 15px;
		font-weight: 600;
		transition: background 0.2s;
	}

	@media (max-width: 720px) {
		.controls-group {
			bottom: 12px;
			right: 12px;
			gap: 8px;
		}
		.zoom-control {
			flex-direction: row;
			border-radius: 10px;
		}
		.zoom-btn {
			width: 40px;
			height: 38px;
			font-size: 20px;
		}
		.zoom-btn:first-child {
			border-bottom: none;
			border-right: 1px solid var(--glassbd);
		}
		.mode-toggle {
			padding: 3px;
		}
		.mode-btn {
			padding: 7px 14px;
			font-size: 12px;
		}
	}
</style>
