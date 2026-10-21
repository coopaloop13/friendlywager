<script lang="ts">
	import { page } from '$app/state';
	import { goto, invalidateAll } from '$app/navigation';
	import { gql } from '#lib/gql.js';
	import { GAME_FIELDS, leagueFrom, type GameView, type PickView, type WeekView } from '#lib/picks.js';
	import GameCard from '#lib/GameCard.svelte';
	import LeagueToggle from '#lib/LeagueToggle.svelte';
	import Landing from '#lib/Landing.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	type W = (WeekView & { games: (GameView & { myPick: PickView | null })[] }) | null;

	const league = $derived(leagueFrom(page.url.searchParams));
	let week = $state<W>(null);
	let loading = $state(true);
	let error = $state('');

	$effect(() => {
		if (!data.user) return;
		const l = league;
		let stale = false;
		loading = true;
		week = null;
		error = '';
		gql<{ currentWeek: W }>(
			`query($l: League!) { currentWeek(league: $l) { league season seasonType week games { ${GAME_FIELDS} myPick { home away } } } }`,
			{ l }
		)
			.then((d) => stale || (week = d.currentWeek))
			.catch((e) => stale || (error = e.message))
			.finally(() => stale || (loading = false));
		return () => (stale = true);
	});

	async function logOut() {
		await gql('mutation { logOut }');
		await invalidateAll();
		await goto('/');
	}
</script>

{#if !data.user}
	<Landing />
{:else}
	<h1>This week</h1>
	<LeagueToggle {league} />
	{#if error}<p class="error" role="alert">{error}</p>{/if}
	{#if loading}
		<p>Loading…</p>
	{:else if !week}
		<p>No games loaded yet.</p>
	{:else}
		<p class="sub">{week.league} {week.season} · week {week.week}</p>
		{#each week.games as g (g.id)}
			<GameCard game={g} pick={g.myPick} />
		{:else}
			<p>No games this week.</p>
		{/each}
	{/if}
	<button class="out" onclick={logOut}>Log out</button>
{/if}

<style>
	.sub {
		color: var(--muted);
		font-family: var(--display);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}
	.out {
		background: none;
		border: none;
		box-shadow: none;
		color: var(--red);
		min-height: 44px;
		margin-top: 1rem;
	}
</style>
