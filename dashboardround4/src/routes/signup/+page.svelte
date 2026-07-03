<script lang="ts">
	import { CATS } from '$lib/design/categories';

	let name = $state('');
	let email = $state('');
	let interests = $state<Set<string>>(new Set());
	let submitting = $state(false);
	let submitted = $state(false);
	let error = $state('');

	function toggleInterest(id: string) {
		const next = new Set(interests);
		if (next.has(id)) next.delete(id);
		else next.add(id);
		interests = next;
	}

	function validEmail(v: string) {
		return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
	}

	function hexToRgb(hex: string): string {
		const h = hex.replace('#', '');
		const r = parseInt(h.substring(0, 2), 16);
		const g = parseInt(h.substring(2, 4), 16);
		const b = parseInt(h.substring(4, 6), 16);
		return `${r},${g},${b}`;
	}

	async function onSubmit(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		if (!name.trim()) {
			error = 'Tell us your name.';
			return;
		}
		if (!validEmail(email)) {
			error = 'Enter a valid email address.';
			return;
		}
		submitting = true;
		await new Promise((r) => setTimeout(r, 700));
		submitting = false;
		submitted = true;
	}
</script>

<svelte:head>
	<title>Sign up — Nave</title>
</svelte:head>

<main class="signup-page">
	<div class="glow" style="background:var(--sky);"></div>

	<div class="lancets">
		<span style="background:linear-gradient(180deg,#a20021,transparent);"></span>
		<span style="background:linear-gradient(180deg,#f3752b,transparent);"></span>
		<span style="background:linear-gradient(180deg,#ee8434,transparent);"></span>
		<span style="background:linear-gradient(180deg,#717ec3,transparent);"></span>
		<span style="background:linear-gradient(180deg,#496ddb,transparent);"></span>
		<span style="background:linear-gradient(180deg,#c95d63,transparent);"></span>
		<span style="background:linear-gradient(180deg,#f52f57,transparent);"></span>
	</div>

	<div class="wrap">
		<div class="glass card">
			{#if submitted}
				<div class="success">
					<div class="check-ring">
						<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0e1220" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
							<polyline points="20 6 9 17 4 12"></polyline>
						</svg>
					</div>
					<p class="kicker" style="margin:14px 0 6px;">You're in</p>
					<h1 class="title">Welcome to Nave, {name.split(' ')[0] || 'friend'}.</h1>
					<p class="body">
						We'll email <strong>{email}</strong> when new regions, categories and data drops land
						on the atlas.
					</p>
					<a href="/" class="btn-gold back-link">Explore the map</a>
				</div>
			{:else}
				<p class="kicker">A Stained-Glass Design System</p>
				<h1 class="title">Follow the churches with us.</h1>
				<p class="body">
					Create a free account to save regions, track new conversions as they're mapped, and get
					notified when the atlas updates.
				</p>

				<form onsubmit={onSubmit} class="form">
					<label class="field">
						<span class="field-label">Name</span>
						<input
							type="text"
							bind:value={name}
							placeholder="Your name"
							autocomplete="name"
							class="input"
						/>
					</label>
					<label class="field">
						<span class="field-label">Email</span>
						<input
							type="email"
							bind:value={email}
							placeholder="you@example.com"
							autocomplete="email"
							class="input"
						/>
					</label>

					<div class="field">
						<span class="field-label">What are you interested in?</span>
						<div class="interest-grid">
							{#each CATS as c (c.id)}
								<button
									type="button"
									class="interest-chip"
									style="background:{interests.has(c.id)
										? `rgba(${hexToRgb(c.color)},.16)`
										: 'none'};border-color:{interests.has(c.id) ? c.color : 'var(--bd)'};"
									onclick={() => toggleInterest(c.id)}
								>
									<span class="swatch" style="background:{c.color};"></span>
									{c.label}
								</button>
							{/each}
						</div>
					</div>

					{#if error}
						<p class="error">{error}</p>
					{/if}

					<button type="submit" class="btn-gold submit-btn" disabled={submitting}>
						{submitting ? 'Creating account…' : 'Create free account'}
					</button>
					<p class="fine-print">
						By continuing you agree this is a demo account for the Nave atlas — no spam, ever.
					</p>
				</form>
			{/if}
		</div>
		<p class="footer-mark">© nave.systems</p>
	</div>
</main>

<style>
	.signup-page {
		position: relative;
		min-height: calc(100dvh - var(--header-h));
		overflow: hidden;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 40px 18px 60px;
	}
	.glow {
		position: absolute;
		inset: 0;
		z-index: 0;
	}
	.lancets {
		position: absolute;
		inset: 0;
		display: flex;
		gap: 3px;
		opacity: 0.1;
		pointer-events: none;
		z-index: 1;
	}
	.lancets span {
		flex: 1;
	}
	.wrap {
		position: relative;
		z-index: 2;
		width: 100%;
		max-width: 440px;
		display: flex;
		flex-direction: column;
		align-items: center;
	}
	.card {
		width: 100%;
		border-radius: 22px;
		padding: clamp(26px, 5vw, 40px);
		animation: tcRise 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
	}
	.title {
		font-family: var(--font-display);
		font-weight: 700;
		font-size: clamp(24px, 4vw, 32px);
		line-height: 1.08;
		letter-spacing: -0.01em;
		margin: 0 0 12px;
		color: var(--tx);
	}
	.body {
		font-size: 14.5px;
		line-height: 1.6;
		color: var(--txd);
		margin: 0 0 24px;
	}
	.form {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}
	.field {
		display: flex;
		flex-direction: column;
		gap: 7px;
	}
	.field-label {
		font-size: 13px;
		font-weight: 500;
		color: var(--txd);
	}
	.input {
		background: var(--bg);
		border: 1px solid var(--bd);
		border-radius: 10px;
		padding: 11px 14px;
		font-size: 14.5px;
		color: var(--tx);
		font-family: var(--font-sans);
		outline: none;
		transition:
			border-color 0.15s,
			box-shadow 0.15s;
	}
	.input:focus {
		border-color: var(--bdg);
		box-shadow: 0 0 0 3px rgba(238, 132, 52, 0.14);
	}
	.interest-grid {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}
	.interest-chip {
		display: inline-flex;
		align-items: center;
		gap: 7px;
		border: 1px solid var(--bd);
		border-radius: 999px;
		padding: 7px 13px;
		font-size: 12.5px;
		color: var(--txd);
		cursor: pointer;
		font-family: var(--font-sans);
		transition:
			border-color 0.15s,
			background 0.15s;
	}
	.interest-chip .swatch {
		width: 8px;
		height: 8px;
		border-radius: 2px;
	}
	.error {
		font-size: 12.5px;
		color: #f3752b;
		margin: -6px 0 0;
	}
	.submit-btn {
		width: 100%;
		padding: 13px 20px;
		font-size: 15px;
		margin-top: 4px;
	}
	.submit-btn:disabled {
		opacity: 0.7;
		cursor: default;
	}
	.fine-print {
		font-size: 11px;
		color: var(--txf);
		text-align: center;
		margin: 2px 0 0;
	}

	.success {
		text-align: center;
		padding: 8px 0;
	}
	.check-ring {
		width: 52px;
		height: 52px;
		border-radius: 50%;
		background: var(--gold);
		display: flex;
		align-items: center;
		justify-content: center;
		margin: 0 auto;
	}
	.success .kicker {
		text-align: center;
	}
	.back-link {
		display: inline-block;
		margin-top: 22px;
		text-decoration: none;
	}

	.footer-mark {
		font-family: var(--font-mono);
		font-size: 10.5px;
		letter-spacing: 0.04em;
		color: var(--txf);
		margin: 22px 0 0;
	}
</style>
