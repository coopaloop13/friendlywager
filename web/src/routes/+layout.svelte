<script lang="ts">
	import favicon from '#lib/assets/favicon.svg';
	import { page } from '$app/state';
	import LoadingOverlay from '#lib/LoadingOverlay.svelte';
	import type { LayoutProps } from './$types';

	let { children, data }: LayoutProps = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<div class="app">
	<header class="field">
		<a href="/" class="brand">🏈 Friendly Wager</a>
		{#if data.user}<span class="me">@{data.user.handle}</span>{/if}
	</header>

	<main class:nav={data.user}>{@render children()}</main>

	{#if data.user}
		<nav class="tabs" aria-label="Main">
			{#each [['/', '🏈', 'This week'], ['/friends', '🤝', 'Friends'], ['/leaderboard', '🏆', 'Leaderboard']] as [href, icon, label]}
				<a {href} aria-current={page.url.pathname === href ? 'page' : undefined}>
					<span aria-hidden="true">{icon}</span>{label}
				</a>
			{/each}
		</nav>
	{/if}
</div>

<LoadingOverlay />

<style>
	:global(:root) {
		--turf: #1f7a3f;
		--turf-dark: #14532d;
		--chalk: #fffdf7;
		--paper: #f3efe3;
		--ink: #1b1b1b;
		--muted: #5f6b62;
		--line: #ddd6c4;
		--gold: #ffc72c;
		--gold-dark: #e0a800;
		--red: #c8102e;
		--leather: #8b4a1f;
		--display: Oswald, system-ui, sans-serif;
		--varsity: Graduate, Georgia, serif;
	}
	:global(body) {
		margin: 0;
		font: 16px/1.5 system-ui, sans-serif;
		color: var(--ink);
		background: var(--paper);
	}
	:global(h1),
	:global(h2) {
		font-family: var(--display);
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--turf-dark);
		margin: 0.5rem 0 0.75rem;
	}
	:global(h1) {
		font-size: 1.9rem;
		border-bottom: 4px solid var(--gold);
		display: inline-block;
	}
	:global(a) {
		color: var(--turf);
		font-weight: 600;
	}
	:global(input),
	:global(button) {
		font: inherit;
		padding: 0.6rem 0.75rem;
		border-radius: 10px;
		border: 2px solid var(--line);
	}
	:global(input) {
		background: #fff;
	}
	:global(input:focus-visible),
	:global(button:focus-visible),
	:global(a:focus-visible) {
		outline: 3px solid var(--gold);
		outline-offset: 2px;
	}
	:global(button) {
		background: var(--gold);
		color: var(--ink);
		border-color: var(--gold-dark);
		font-family: var(--display);
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		cursor: pointer;
		box-shadow: 0 3px 0 var(--gold-dark);
		transition: transform 0.05s;
	}
	:global(button:active) {
		transform: translateY(2px);
		box-shadow: 0 1px 0 var(--gold-dark);
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
		color: var(--red);
		font-weight: 600;
	}
	.field {
		position: sticky;
		top: 0;
		z-index: 10;
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.75rem 1rem;
		background: var(--turf-dark) repeating-linear-gradient(90deg, transparent 0 48px, rgb(255 255 255 / 0.1) 48px 50px);
		border-bottom: 4px solid var(--gold);
		color: #fff;
	}
	.brand {
		font-family: var(--varsity);
		font-size: 1.25rem;
		color: #fff;
		text-decoration: none;
		text-shadow: 0 2px 0 rgb(0 0 0 / 0.35);
	}
	.me {
		font-family: var(--display);
		color: var(--gold);
	}
	main.nav {
		padding-bottom: 5.5rem;
	}
	.tabs {
		position: fixed;
		bottom: 0;
		left: 0;
		right: 0;
		display: flex;
		background: #111;
		border-top: 3px solid var(--gold);
		padding-bottom: env(safe-area-inset-bottom);
	}
	.tabs a {
		flex: 1;
		min-height: 60px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		text-decoration: none;
		color: #bbb;
		font-family: var(--display);
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}
	.tabs a span {
		font-size: 1.25rem;
		line-height: 1.2;
	}
	.tabs a[aria-current] {
		color: var(--gold);
		background: #1d1d1d;
	}
	main {
		max-width: 28rem;
		margin: 0 auto;
		padding: 1rem;
	}
</style>
