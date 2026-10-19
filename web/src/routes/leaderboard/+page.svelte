<script lang="ts">
	import { page } from '$app/state';
	import { gql } from '#lib/gql.js';
	import { leagueFrom } from '#lib/picks.js';
	import LeagueToggle from '#lib/LeagueToggle.svelte';

	type Row = { userId: string; handle: string; correctWinners: number; avgCloseness: number | null };
	const league = $derived(leagueFrom(page.url.searchParams));
	let rows = $state<Row[] | null>(null); // null = no season data
	let loading = $state(true);
	let error = $state('');

	$effect(() => {
		const l = league;
		let stale = false;
		loading = true;
		rows = null;
		error = '';
		gql<{ currentWeek: { season: number } | null }>(
			'query($l: League!) { currentWeek(league: $l) { season } }',
			{ l }
		)
			.then(async ({ currentWeek }) => {
				if (stale || !currentWeek) return;
				const d = await gql<{ leaderboard: Row[] }>(
					'query($l: League!, $s: Int!) { leaderboard(league: $l, season: $s) { userId handle correctWinners avgCloseness } }',
					{ l, s: currentWeek.season }
				);
				if (!stale) rows = d.leaderboard;
			})
			.catch((e) => stale || (error = e.message))
			.finally(() => stale || (loading = false));
		return () => (stale = true);
	});
</script>

<h1>Leaderboard</h1>
<LeagueToggle {league} />
{#if error}<p class="error" role="alert">{error}</p>{/if}
{#if loading}
	<p>Loading…</p>
{:else if !rows}
	<p>No games loaded yet.</p>
{:else if !rows.length}
	<p>No results yet.</p>
{:else}
	<table>
		<thead><tr><th>#</th><th>Player</th><th>Winners</th><th>Avg closeness</th></tr></thead>
		<tbody>
			{#each rows as r, i (r.userId)}
				<tr>
					<td>{i + 1}</td>
					<td>@{r.handle}</td>
					<td>{r.correctWinners}</td>
					<td>{r.avgCloseness === null ? '–' : r.avgCloseness.toFixed(1)}</td>
				</tr>
			{/each}
		</tbody>
	</table>
{/if}

<style>
	table {
		width: 100%;
		border-collapse: collapse;
	}
	th,
	td {
		text-align: left;
		padding: 0.6rem 0.4rem;
		border-bottom: 1px solid #eee;
	}
</style>
