<script lang="ts">
	import { page } from '$app/state';
	import { goto, invalidateAll } from '$app/navigation';
	import { gql } from '#lib/gql.js';
	import { GAME_FIELDS, leagueFrom, type GameView, type PickView, type WeekView } from '#lib/picks.js';
	import GameCard from '#lib/GameCard.svelte';
	import LeagueToggle from '#lib/LeagueToggle.svelte';

	type W = (WeekView & { games: (GameView & { myPick: PickView | null })[] }) | null;

	const league = $derived(leagueFrom(page.url.searchParams));
	let week = $state<W>(null);
	let loading = $state(true);
	let error = $state('');

	$effect(() => {
		const l = league;
		loading = true;
		error = '';
		gql<{ currentWeek: W }>(
			`query($l: League!) { currentWeek(league: $l) { league season seasonType week games { ${GAME_FIELDS} myPick { home away } } } }`,
			{ l }
		)
			.then((d) => (week = d.currentWeek))
			.catch((e) => (error = e.message))
			.finally(() => (loading = false));
	});

	async function logOut() {
		await gql('mutation { logOut }');
		await invalidateAll();
		await goto('/login');
	}
</script>

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

<style>
	.sub {
		color: #666;
	}
	.out {
		background: none;
		color: #1a5fd0;
		min-height: 44px;
		margin-top: 1rem;
	}
</style>
