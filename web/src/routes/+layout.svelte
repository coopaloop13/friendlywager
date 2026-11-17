<script lang="ts">
	import favicon from '#lib/assets/favicon.svg';
	import { invalidateAll } from '$app/navigation';
	import { page } from '$app/state';
	import LoadingOverlay from '#lib/LoadingOverlay.svelte';
	import { applyLook, getLook } from '#lib/look.js';
	import { enablePush } from '#lib/push.js';
	import type { LayoutProps } from './$types';

	let { children, data }: LayoutProps = $props();

	// store apps: once someone is signed in, this phone gets their "picks lock soon" reminders
	$effect(() => {
		if (data.user) enablePush();
	});

	// app.html already set the look on <html>; this matches the browser's own bar to it
	$effect(() => applyLook(getLook()));

	// keep asking while the API is down; a cold start takes a couple of minutes
	$effect(() => {
		if (!data.unavailable) return;
		const t = setInterval(invalidateAll, 10_000);
		return () => clearInterval(t);
	});
</script>

<svelte:head>
	<title>Pick'ems: Box Score Picks</title>
	<link rel="icon" href={favicon} />
</svelte:head>

<div class="app">
	<header class="top">
		<a href="/" class="brand">Pick'ems</a>
		{#if data.user}<a class="me" href="/settings" aria-label="Settings for @{data.user.handle}">@{data.user.handle} ⚙︎</a>{/if}
	</header>

	<main class:nav={data.user}>
		{#if data.unavailable}
			<h1>Timeout on the field</h1>
			<p role="status">We can't reach the server right now. It may be warming up, which takes a couple of minutes. This page retries on its own.</p>
			<button onclick={invalidateAll}>Try again</button>
		{:else}
			{@render children()}
		{/if}
	</main>

	{#if data.user}
		<nav class="tabs" aria-label="Main">
			{#each [['/', 'This week'], ['/friends', 'Friends'], ['/leaderboard', 'Leaderboard']] as [href, label]}
				<a {href} aria-current={page.url.pathname === href ? 'page' : undefined}>{label}</a>
			{/each}
		</nav>
	{/if}
</div>

<LoadingOverlay />

<style>
	/* Two looks, chosen in Settings (lib/look.ts). Components use only these tokens, so a look is one block here. */
	:global(:root) {
		/* Backyard: enamel white, navy rim, mustard */
		--ground: #f3f4f0;
		--surface: #fff;
		--well: #eef0ea;
		--bar: #fff;
		--ink: #1b2a45;
		--muted: #5d6880;
		--line: #1b2a45; /* card and button outlines */
		--rule: #b9bfcb; /* dividers and quiet borders */
		--link: #1b2a45;
		--accent: #e0aa1e;
		--on-accent: #1b2a45;
		--inv: #1b2a45;
		--on-inv: #fff;
		--sel: #1b2a45; /* the chosen side of a toggle */
		--on-sel: #fff;
		--tile: transparent; /* behind a score */
		--on-tile: #1b2a45;
		--good: #1f7a4d;
		--bad: #b3261e;
		--on-bad: #fff;
		--radius: 20px;
		--radius-s: 14px;
		--pill: 99px;
		--display: 'Bricolage Grotesque', system-ui, sans-serif;
		--body: Figtree, system-ui, sans-serif;
		--num: 'Bricolage Grotesque', system-ui, sans-serif;
		--caps: none;
		--brand-case: lowercase;
		--track: -0.02em;
		--stretch: 100%;
		--h1: 1.9rem;
		color-scheme: light;
	}
	:global(:root[data-look='s112']) {
		/* Section 112: night game. Concrete, black signage, one hi-vis orange */
		--ground: #161817;
		--surface: #232624;
		--well: #0c0d0c;
		--bar: #0c0d0c;
		--ink: #f2f2ee;
		--muted: #a3a9a4;
		--line: transparent;
		--rule: #3f4541;
		--link: #ff7a47;
		--accent: #ff5a1f;
		--on-accent: #111312;
		--inv: #0c0d0c;
		--on-inv: #f2f2ee;
		--sel: #ff5a1f;
		--on-sel: #111312;
		--tile: #0c0d0c;
		--on-tile: #ff5a1f;
		--good: #5fd08a;
		--bad: #ff7a6b;
		--on-bad: #111312;
		--radius: 4px;
		--radius-s: 2px;
		--pill: 2px;
		--display: Archivo, system-ui, sans-serif;
		--body: Archivo, system-ui, sans-serif;
		--num: 'Martian Mono', ui-monospace, monospace;
		--caps: uppercase;
		--brand-case: uppercase;
		--track: 0.03em;
		--stretch: 72%;
		--h1: 2.4rem;
		color-scheme: dark;
	}
	:global(body) {
		margin: 0;
		font: 16px/1.5 var(--body);
		color: var(--ink);
		background: var(--ground);
	}
	:global(h1),
	:global(h2) {
		font-family: var(--display);
		font-weight: 800;
		font-stretch: var(--stretch);
		text-transform: var(--caps);
		letter-spacing: var(--track);
		line-height: 1.1;
		text-wrap: balance;
		margin: 0.5rem 0 0.75rem;
	}
	:global(h1) {
		font-size: var(--h1);
	}
	:global(h2) {
		font-size: 1.25rem;
	}
	:global(a) {
		color: var(--link);
		font-weight: 600;
	}
	:global(input),
	:global(button) {
		font: inherit;
		padding: 0.6rem 0.9rem;
		border-radius: var(--radius-s);
		border: 2px solid var(--rule);
	}
	:global(input) {
		background: var(--surface);
		color: var(--ink);
	}
	:global(input:focus-visible),
	:global(button:focus-visible),
	:global(a:focus-visible),
	:global(summary:focus-visible) {
		outline: 3px solid var(--ink);
		outline-offset: 2px;
	}
	:global(button) {
		background: var(--accent);
		color: var(--on-accent);
		border-color: var(--line);
		border-radius: var(--pill);
		font-family: var(--display);
		font-weight: 700;
		text-transform: var(--caps);
		cursor: pointer;
		box-shadow: 0 3px 0 var(--line);
		transition: transform 0.05s;
	}
	:global(button:active) {
		transform: translateY(2px);
		box-shadow: 0 1px 0 var(--line);
	}
	:global(button:disabled) {
		opacity: 0.5;
		cursor: default;
	}
	:global(label) {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		font-weight: 600;
	}
	:global(form) {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	:global(.error) {
		color: var(--bad);
		font-weight: 600;
	}
	.top {
		position: sticky;
		top: 0;
		z-index: 10;
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.75rem 1rem;
		padding-top: calc(0.75rem + env(safe-area-inset-top)); /* clear the phone's status bar in the app */
		background: var(--bar);
		border-bottom: 2px solid var(--line);
	}
	.brand {
		font: 800 1.35rem var(--display);
		font-stretch: var(--stretch);
		text-transform: var(--brand-case);
		letter-spacing: var(--track);
		color: var(--ink);
		text-decoration: none;
	}
	.brand::after {
		content: '';
		display: inline-block;
		width: 0.45rem;
		height: 0.45rem;
		margin-left: 0.2rem;
		border-radius: var(--pill);
		background: var(--accent);
	}
	.me {
		font-size: 0.9rem;
		color: var(--muted);
		text-decoration: none;
		padding: 0.5rem 0;
	}
	main {
		max-width: 28rem;
		margin: 0 auto;
		padding: 1rem;
	}
	main.nav {
		padding-bottom: calc(5.5rem + env(safe-area-inset-bottom));
	}
	.tabs {
		position: fixed;
		bottom: calc(0.75rem + env(safe-area-inset-bottom));
		left: 0.75rem;
		right: 0.75rem;
		max-width: 26.5rem;
		margin: 0 auto;
		display: flex;
		padding: 5px;
		background: var(--inv);
		border-radius: var(--pill);
		box-shadow: 0 6px 18px rgb(0 0 0 / 0.25);
	}
	.tabs a {
		flex: 1;
		min-height: 46px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--pill);
		text-decoration: none;
		color: var(--on-inv);
		opacity: 0.75;
		font-family: var(--display);
		font-size: 0.85rem;
		font-weight: 700;
		text-transform: var(--caps);
	}
	.tabs a[aria-current] {
		opacity: 1;
		background: var(--accent);
		color: var(--on-accent);
	}
</style>
