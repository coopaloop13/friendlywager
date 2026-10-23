<script lang="ts">
	import { page } from '$app/state';
	import { gql } from '#lib/gql.js';
	import { leagueFrom } from '#lib/picks.js';
	import LeagueToggle from '#lib/LeagueToggle.svelte';

	type Row = {
		userId: string; handle: string;
		pointsFor: number; pointsAgainst: number; weeksWon: number; weeksLost: number; weeksTied: number;
	};
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
					'query($l: League!, $s: Int!) { leaderboard(league: $l, season: $s) { userId handle pointsFor pointsAgainst weeksWon weeksLost weeksTied } }',
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
	<p>Add friends to see your record against them.</p>
{:else}
	<table>
		<thead><tr><th>vs</th><th>Weeks</th><th>Points</th></tr></thead>
		<tbody>
			{#each rows as r (r.userId)}
				<tr>
					<td><a href="/matchup/{r.userId}?league={league}">@{r.handle}</a></td>
					<td>{r.weeksWon}W {r.weeksLost}L {r.weeksTied}T</td>
					<td>{r.pointsFor}–{r.pointsAgainst}</td>
				</tr>
			{/each}
		</tbody>
	</table>
{/if}

<style>
	table {
		width: 100%;
		border-collapse: collapse;
		background: var(--chalk);
		border-radius: 14px;
		overflow: hidden;
		box-shadow: 0 2px 6px rgb(0 0 0 / 0.06);
	}
	th {
		background: #111;
		color: var(--gold);
		font-family: var(--display);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		font-size: 0.8rem;
		font-weight: 500;
	}
	th,
	td {
		text-align: left;
		padding: 0.6rem 0.5rem;
		border-bottom: 1px solid var(--line);
	}
</style>
