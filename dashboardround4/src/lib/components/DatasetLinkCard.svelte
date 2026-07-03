<script lang="ts">
	const DATASET_URL =
		'https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi%3A10.7910%2FDVN%2F4AN2FL&version=DRAFT';
</script>

<a class="glass card" href={DATASET_URL} target="_blank" rel="noopener noreferrer">
	<div class="text">
		<p class="kicker">Open data</p>
		<p class="title">Get the full dataset</p>
		<p class="caption">23,000+ coordinate-level records, CC BY 4.0, citable via Harvard Dataverse.</p>
	</div>
	<span class="arrow" aria-hidden="true">→</span>
</a>

<style>
	.card {
		position: absolute;
		bottom: 232px;
		left: 28px;
		z-index: 420;
		width: 25%;
		min-width: 320px;
		max-width: 480px;
		border-radius: 20px;
		padding: 20px 24px;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		text-decoration: none;
		transition: border-color 0.15s;
	}
	.card:hover {
		border-color: var(--bdg);
	}
	.title {
		font-family: var(--font-display);
		font-weight: 600;
		font-size: 19px;
		color: var(--tx);
		margin: 0 0 6px;
	}
	.caption {
		font-size: 13.5px;
		line-height: 1.5;
		color: var(--txd);
		margin: 0;
		max-width: 46ch;
	}
	.arrow {
		flex-shrink: 0;
		font-size: 22px;
		color: var(--gold);
	}

	@media (max-width: 1080px) {
		.card {
			position: static;
			width: 100%;
			min-width: 0;
			max-width: none;
			flex-wrap: wrap;
			border-radius: 16px;
			padding: 18px 20px;
		}
		.title {
			font-size: 17px;
		}
		.caption {
			font-size: 12.5px;
		}
	}
</style>
