<script lang="ts">
	import { resolveSelection, donutForMix, donutTitle } from '$lib/viewmodel';

	let sel = $derived(resolveSelection());
	let donut = $derived(donutForMix(sel.mix || []));
	let title = $derived(donutTitle(sel));
</script>

<div class="glass donut-card">
	<p class="kicker" style="text-align:center;margin-bottom:2px;">{title}</p>
	<div class="donut-wrap">
		<svg viewBox="0 0 224 200" class="donut-svg">
			<g transform="rotate(-90 112 100)">
				<circle cx="112" cy="100" r="26" fill="none" stroke="var(--bg3)" stroke-width="18"></circle>
				{#each donut.segs as s, i (i)}
					<circle
						cx="112"
						cy="100"
						r="26"
						fill="none"
						stroke={s.color}
						stroke-width="18"
						stroke-dasharray={s.dash}
						stroke-dashoffset={s.offset}
						class="donut-seg"
					></circle>
				{/each}
			</g>
			{#each donut.donutLeaders as l, i (i)}
				<polyline points={l.points} fill="none" stroke={l.color} stroke-width="1" opacity="0.6"
				></polyline>
			{/each}
		</svg>
		{#each donut.donutLeaders as l, i (i)}
			<div
				class="leader-label"
				style="left:{l.lp}%;top:{l.tp}%;transform:{l.tf};text-align:{l.align};max-width:{l.align ===
				'left'
					? `calc(100% - ${l.lp}% - 6px)`
					: `calc(${l.lp}% - 6px)`};"
			>
				<span class="leader-name">{l.label}</span>
				<span class="leader-pct" style="color:{l.color};">{l.pct}</span>
			</div>
		{/each}
	</div>
</div>

<style>
	.donut-card {
		width: 100%;
		border-radius: 20px;
		padding: 20px 24px 14px;
	}
	.donut-wrap {
		position: relative;
		overflow: hidden;
	}
	.donut-svg {
		width: 100%;
		height: auto;
		display: block;
	}
	.donut-seg {
		transition:
			stroke-dasharray 0.5s ease,
			stroke-dashoffset 0.5s ease;
	}
	.leader-label {
		position: absolute;
		line-height: 1.25;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		pointer-events: none;
	}
	.leader-name {
		font-size: 13px;
		font-weight: 600;
		color: var(--tx);
	}
	.leader-pct {
		font-size: 13px;
		font-weight: 800;
		margin-left: 4px;
	}

	@media (max-width: 1080px) {
		.donut-card {
			border-radius: 16px;
			padding: 16px 12px 12px;
		}
		.leader-name,
		.leader-pct {
			font-size: 10.5px;
		}
	}
</style>
