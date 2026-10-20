<script lang="ts">
	import { navigating } from '$app/state';
	import { pending } from '#lib/gql.js';
	import Football from '#lib/Football.svelte';

	const LINES = ['Hiking the ball…', 'Checking the replay…', 'Huddling up…', 'Reading the defense…', 'Moving the chains…'];

	const busy = $derived($pending > 0 || !!navigating.to);
	let show = $state(false);
	let line = $state(LINES[0]);

	// Delay so fast requests don't flash the overlay.
	$effect(() => {
		if (!busy) return void (show = false);
		const t = setTimeout(() => {
			line = LINES[Math.floor(Math.random() * LINES.length)];
			show = true;
		}, 250);
		return () => clearTimeout(t);
	});
</script>

{#if show}
	<div class="overlay" role="alertdialog" aria-modal="true" aria-busy="true" aria-label="Loading">
		<div class="box">
			<Football />
			<p role="status">{line}</p>
		</div>
	</div>
{/if}

<style>
	.overlay {
		position: fixed;
		inset: 0;
		z-index: 100;
		display: grid;
		place-items: center;
		background: rgb(10 30 18 / 0.55);
		backdrop-filter: blur(2px);
		animation: fade 0.15s ease-out;
	}
	.box {
		background: var(--chalk);
		border: 3px solid var(--gold);
		border-radius: 16px;
		padding: 1.25rem 2rem;
		text-align: center;
		box-shadow: 0 10px 30px rgb(0 0 0 / 0.35);
	}
	p {
		margin: 0.5rem 0 0;
		font-family: var(--display);
		color: var(--turf-dark);
	}
	@keyframes fade {
		from {
			opacity: 0;
		}
	}
</style>
