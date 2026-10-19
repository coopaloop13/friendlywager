<script lang="ts">
	import favicon from '#lib/assets/favicon.svg';
	import { page } from '$app/state';
	import type { LayoutProps } from './$types';

	let { children, data }: LayoutProps = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<main class:nav={data.user}>{@render children()}</main>

{#if data.user}
	<nav class="tabs" aria-label="Main">
		{#each [['/', 'This week'], ['/friends', 'Friends'], ['/leaderboard', 'Leaderboard']] as [href, label]}
			<a {href} aria-current={page.url.pathname === href ? 'page' : undefined}>{label}</a>
		{/each}
	</nav>
{/if}

<style>
	:global(body) {
		margin: 0;
		font: 16px/1.5 system-ui, sans-serif;
		color: #1a1a1a;
		background: #fafafa;
	}
	:global(input),
	:global(button) {
		font: inherit;
		padding: 0.6rem 0.75rem;
		border-radius: 8px;
		border: 1px solid #bbb;
	}
	:global(button) {
		background: #1a5fd0;
		color: #fff;
		border-color: #1a5fd0;
		cursor: pointer;
	}
	:global(label) {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	:global(form) {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	:global(.error) {
		color: #b00020;
	}
	main.nav {
		padding-bottom: 5rem;
	}
	.tabs {
		position: fixed;
		bottom: 0;
		left: 0;
		right: 0;
		display: flex;
		background: #fff;
		border-top: 1px solid #ddd;
	}
	.tabs a {
		flex: 1;
		min-height: 56px;
		display: flex;
		align-items: center;
		justify-content: center;
		text-decoration: none;
		color: #555;
	}
	.tabs a[aria-current] {
		color: #1a5fd0;
		font-weight: 600;
	}
	main {
		max-width: 28rem;
		margin: 0 auto;
		padding: 1rem;
	}
</style>
