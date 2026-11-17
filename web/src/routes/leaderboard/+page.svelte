<script lang="ts">
	import { page } from '$app/state';
	import { cached, gql, remember } from '#lib/gql.js';
	import { leagueFrom } from '#lib/picks.js';
	import LeagueToggle from '#lib/LeagueToggle.svelte';
	import {
		BOARD_QUERY,
		CURRENT_WEEK_QUERY,
		diff,
		lead,
		outcome,
		pct,
		settled,
		sortRows,
		streak,
		summary,
		thisWeek,
		weekLabel,
		type Row,
		type SortBy,
		type Stats
	} from '#lib/standings.js';

	type Week = { seasonType: number; week: number };
	const league = $derived(leagueFrom(page.url.searchParams));
	let rows = $state<Row[] | null>(null); // null = no season data
	let stats = $state<Stats | null>(null);
	let cur = $state<Week | null>(null);
	let sortBy = $state<SortBy>('weeks');
	let loading = $state(true);
	let error = $state('');
	const shown = $derived(rows ? sortRows(rows, sortBy) : []);
	const s = $derived(summary(shown));
	const signed = (n: number) => (n > 0 ? `+${n}` : `${n}`);

	$effect(() => {
		const l = league;
		const key = `board:${page.data.user?.id}:${l}`;
		let stale = false;
		// show the last copy at once (finished weeks never change), refresh quietly
		const hit = cached<{ rows: Row[]; stats: Stats; cur: Week }>(key);
		rows = hit?.rows ?? null;
		stats = hit?.stats ?? null;
		cur = hit?.cur ?? null;
		loading = !hit;
		error = '';
		const quiet = !!hit;
		gql<{ currentWeek: ({ season: number } & Week) | null }>(CURRENT_WEEK_QUERY, { l }, fetch, { quiet })
			.then(async ({ currentWeek }) => {
				if (stale || !currentWeek) return;
				const d = await gql<{ leaderboard: Row[]; seasonStats: Stats }>(
					BOARD_QUERY,
					{ l, s: currentWeek.season },
					fetch,
					{ quiet }
				);
				if (stale) return;
				rows = d.leaderboard;
				stats = d.seasonStats;
				cur = currentWeek;
				remember(key, { rows: d.leaderboard, stats: d.seasonStats, cur: currentWeek });
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
{:else if !rows || !cur}
	<p>No games loaded yet.</p>
{:else}
	{#if rows.length}
		<div class="board">
			<div class="big">{s.won}-{s.lost}-{s.tied}</div>
			<div>Points {s.pointsFor}–{s.pointsAgainst}</div>
		</div>
	{/if}
	{#if stats}
		{@const p = pct(stats.winners, stats.picked)}
		<section class="card">
			<h2>Your season</h2>
			<p>{stats.picked} picked · {stats.winners} winners{p ? ` (${p})` : ''} · {stats.exact} exact</p>
		</section>
	{/if}
	{#if !rows.length}
		<p>Add friends to see your record against them. <a href="/friends">Find friends</a></p>
	{:else}
		<div class="sort" role="group" aria-label="Sort by">
			<button aria-pressed={sortBy === 'weeks'} onclick={() => (sortBy = 'weeks')}>Weeks won</button>
			<button aria-pressed={sortBy === 'points'} onclick={() => (sortBy = 'points')}>Point diff</button>
		</div>
		{#each shown as r (r.userId)}
			{@const d = diff(r)}
			{@const done = settled(r.weeks, cur)}
			{@const st = streak(done)}
			{@const w = thisWeek(r.weeks, cur)}
			<details class="card" data-lead={lead(r)}>
				<summary>
					<a href="/matchup/{r.userId}?league={league}">@{r.handle}</a>
					<span class="big">{r.weeksWon}-{r.weeksLost}-{r.weeksTied}</span>
					<span class:pos={d > 0} class:neg={d < 0}>{signed(d)}</span>
					{#if st}<span class="chip">{st}</span>{/if}
					<span class="this-week">
						{#if w}{weekLabel(w)}: you {w.pointsFor} – {w.pointsAgainst} them{:else}{weekLabel(cur)}: no picks in play{/if}
					</span>
				</summary>
				{#if done.length}
					<ol class="weeks">
						{#each done as wk (`${wk.seasonType}-${wk.week}`)}
							<li class={outcome(wk)}>{weekLabel(wk)} {outcome(wk)} {wk.pointsFor}–{wk.pointsAgainst}</li>
						{/each}
					</ol>
				{:else}
					<p class="meta">No weeks yet.</p>
				{/if}
			</details>
		{/each}
	{/if}
{/if}

<style>
	.board {
		font-family: var(--display);
		text-align: center;
		background: var(--inv);
		color: var(--on-inv);
		border-radius: var(--radius);
		padding: 0.75rem;
		margin-bottom: 0.75rem;
	}
	.board .big {
		font-family: var(--num);
		font-size: 2.2rem;
		font-weight: 800;
		line-height: 1.2;
	}
	.card {
		background: var(--surface);
		border: 2px solid var(--line);
		border-radius: var(--radius);
		padding: 0.75rem;
		margin-bottom: 0.75rem;
	}
	.card h2 {
		font-size: 1rem;
		margin: 0;
	}
	.card p {
		margin: 0.25rem 0;
	}
	summary {
		list-style: none;
		cursor: pointer;
		min-height: 44px;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
	}
	summary::-webkit-details-marker {
		display: none;
	}
	summary .big {
		font-family: var(--num);
		font-size: 1.3rem;
		font-weight: 800;
		margin-left: auto;
	}
	.this-week {
		flex-basis: 100%;
		color: var(--muted);
		font-size: 0.85rem;
	}
	.pos {
		color: var(--good);
	}
	.neg {
		color: var(--bad);
	}
	.chip,
	.weeks li {
		font-family: var(--display);
		font-size: 0.8rem;
		border-radius: var(--pill);
		padding: 0 0.5rem;
		border: 1px solid var(--rule);
	}
	.weeks {
		list-style: none;
		padding: 0;
		margin: 0.5rem 0 0;
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
	}
	.weeks .W {
		background: var(--accent);
		border-color: var(--accent);
		color: var(--on-accent);
	}
	.weeks .L {
		color: var(--bad);
	}
	.weeks .T {
		color: var(--muted);
	}
	.meta {
		color: var(--muted);
		font-size: 0.85rem;
	}
	.sort {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
	}
	.sort button {
		flex: 1;
		min-height: 44px;
		border-color: var(--rule);
		background: var(--surface);
		color: var(--muted);
		box-shadow: none;
	}
	.sort button[aria-pressed='true'] {
		border-color: var(--sel);
		background: var(--sel);
		color: var(--on-sel);
	}
</style>
