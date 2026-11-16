<script lang="ts">
	import { page } from '$app/state';
	import { cached, gql, remember } from '#lib/gql.js';
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
		const key = `week:${data.user.id}:${l}`;
		let stale = false;
		// show the last copy at once (finished games never change), refresh quietly.
		// `hit` stays local: reading `week` here would make the effect depend on what it writes.
		const hit = cached<W>(key);
		week = hit;
		loading = !hit;
		error = '';
		gql<{ currentWeek: W }>(
			`query($l: League!) { currentWeek(league: $l) { league season seasonType week games { ${GAME_FIELDS} myPick { home away } } } }`,
			{ l },
			fetch,
			{ quiet: !!hit }
		)
			.then((d) => {
				if (stale) return;
				week = d.currentWeek;
				remember(key, week);
			})
			.catch((e) => stale || (error = e.message))
			.finally(() => stale || (loading = false));
		return () => (stale = true);
	});

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
		<!-- keyed on the pick too: a card from the cached copy is rebuilt when the refresh brings a different pick -->
		{#each week.games as g (`${g.id}:${g.myPick?.home}:${g.myPick?.away}`)}
			<GameCard game={g} pick={g.myPick} />
		{:else}
			<p>No games this week.</p>
		{/each}
	{/if}
{/if}

<style>
	.sub {
		color: var(--muted);
		font-family: var(--display);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}
</style>
