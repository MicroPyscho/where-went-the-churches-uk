<script lang="ts">
	const LINKS = [
		{
			name: 'GitHub',
			href: 'https://github.com/MicroPyscho/where-went-the-churches-uk',
			kind: 'svg' as const
		},
		{ name: 'LinkedIn', href: 'http://linkedin.com/in/kelechi-o-collins', kind: 'svg' as const },
		{
			name: 'Harvard Dataverse',
			href: 'https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi%3A10.7910%2FDVN%2F4AN2FL&version=DRAFT',
			kind: 'mono' as const,
			mono: 'D'
		},
		{
			name: 'Kaggle',
			href: 'https://www.kaggle.com/datasets/kelechicollins/where-went-uk-churches',
			kind: 'mono' as const,
			mono: 'K'
		},
		{ name: 'Zenodo', href: 'https://zenodo.org/records/21128772', kind: 'mono' as const, mono: 'Z' }
	];
</script>

<div class="footer-links">
	{#each LINKS as l (l.name)}
		<a
			class="icon-link"
			href={l.href}
			target="_blank"
			rel="noopener noreferrer"
			aria-label={l.name}
			title={l.name}
		>
			{#if l.name === 'GitHub'}
				<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
					<path
						d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.725-4.042-1.61-4.042-1.61-.546-1.385-1.333-1.755-1.333-1.755-1.09-.745.084-.729.084-.729 1.205.084 1.84 1.237 1.84 1.237 1.07 1.834 2.807 1.304 3.492.997.108-.775.42-1.305.762-1.605-2.665-.303-5.466-1.332-5.466-5.93 0-1.31.468-2.38 1.235-3.22-.123-.303-.535-1.523.117-3.176 0 0 1.008-.322 3.3 1.23A11.5 11.5 0 0112 5.803c1.02.005 2.045.138 3.003.404 2.29-1.552 3.297-1.23 3.297-1.23.653 1.653.24 2.873.118 3.176.77.84 1.233 1.91 1.233 3.22 0 4.61-2.804 5.624-5.475 5.92.43.372.823 1.102.823 2.222 0 1.606-.014 2.896-.014 3.286 0 .32.216.694.825.576C20.565 21.796 24 17.297 24 12c0-6.63-5.373-12-12-12z"
					></path>
				</svg>
			{:else if l.name === 'LinkedIn'}
				<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
					<path
						d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"
					></path>
				</svg>
			{:else}
				<span class="mono">{l.mono}</span>
			{/if}
		</a>
	{/each}
</div>

<style>
	.footer-links {
		position: absolute;
		bottom: 20px;
		left: 50%;
		transform: translateX(-50%);
		z-index: 430;
		display: flex;
		align-items: center;
		gap: 12px;
	}
	.icon-link {
		width: 40px;
		height: 40px;
		border-radius: 50%;
		border: 1px solid var(--bd);
		background: var(--bg2);
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--tx);
		text-decoration: none;
		transition:
			border-color 0.15s,
			transform 0.15s;
	}
	.icon-link:hover {
		border-color: var(--bdg);
		transform: translateY(-2px);
	}
	.mono {
		font-family: var(--font-display);
		font-weight: 700;
		font-size: 15px;
	}

	@media (max-width: 1080px) {
		.footer-links {
			position: static;
			transform: none;
			justify-content: center;
			width: 100%;
			gap: 10px;
			padding: 8px 0 4px;
		}
		.icon-link {
			width: 44px;
			height: 44px;
		}
	}
</style>
