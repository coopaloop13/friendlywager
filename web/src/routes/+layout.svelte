<script lang="ts">
	import favicon from '#lib/assets/favicon.svg';
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<main>{@render children()}</main>

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
	main {
		max-width: 28rem;
		margin: 0 auto;
		padding: 1rem;
	}
</style>
