<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import { gql } from '#lib/gql.js';
	import {
		GAME_FIELDS,
		fmtKickoff,
		isLocked,
		leagueFrom,
		teamLabel,
		type GameView,
		type PickView,
		type WeekView
	} from '#lib/picks.js';
	import LeagueToggle from '#lib/LeagueToggle.svelte';

	type MG = { game: GameView; mine: PickView | null; theirs: PickView | null; point: string | null };
	type M = { games: MG[]; myPoints: number; theirPoints: number };
	type H = { pointsFor: number; pointsAgainst: number; weeksWon: number; weeksLost: number; weeksTied: number };

	const friendId = $derived(page.params.friendId ?? "");
	const league = $derived(leagueFrom(page.url.searchParams));
	let wk = $state<WeekView | null>(null);
	let m = $state<M | null>(null);
	let h = $state<H | null>(null);
	let now = $state(new Date());
	onMount(() => {
		const t = setInterval(() => (now = new Date()), 30_000);
		return () => clearInterval(t);
	});
	let loading = $state(true);
	let error = $state('');

	const MATCHUP = `query($f: ID!, $l: League!, $s: Int!, $t: Int!, $w: Int!) {
		matchup(friendId: $f, league: $l, season: $s, seasonType: $t, week: $w) {
			myPoints theirPoints games { mine { home away } theirs { home away } point game { ${GAME_FIELDS} } } } }`;

	let token = 0; // only the latest request may apply its result

	async function loadWeek(l: typeof league, w: WeekView, f: string) {
		const mine = ++token;
		wk = w;
		m = null;
		loading = true;
		error = '';
		try {
			const [d, hh] = await Promise.all([
				gql<{ matchup: M }>(MATCHUP, { f, l, s: w.season, t: w.seasonType, w: w.week }),
				gql<{ headToHead: H }>(
					'query($f: ID!, $l: League!, $s: Int!) { headToHead(friendId: $f, league: $l, season: $s) { pointsFor pointsAgainst weeksWon weeksLost weeksTied } }',
					{ f, l, s: w.season }
				)
			]);
			if (mine !== token) return;
			m = d.matchup;
			h = hh.headToHead;
		} catch (e) {
			if (mine === token) error = (e as Error).message;
		} finally {
			if (mine === token) loading = false;
		}
	}

	$effect(() => {
		const l = league;
		const f = friendId;
		const mine = ++token;
		wk = m = h = null;
		error = '';
		loading = true;
		gql<{ currentWeek: WeekView | null }>(
			'query($l: League!) { currentWeek(league: $l) { league season seasonType week } }',
			{ l }
		)
			.then((d) => {
				if (mine !== token) return;
				if (d.currentWeek) return loadWeek(l, d.currentWeek, f);
				loading = false;
			})
			.catch((e) => {
				if (mine !== token) return;
				error = e.message;
				loading = false;
			});
	});

	function step(d: number) {
		if (wk && wk.week + d >= 1) return loadWeek(league, { ...wk, week: wk.week + d }, friendId);
	}

	const pickText = (g: GameView, p: PickView) => `${g.awayAbbr} ${p.away} – ${g.homeAbbr} ${p.home}`;
</script>

<p><a href="/friends">← Friends</a></p>
<h1>Matchup</h1>
<LeagueToggle {league} />
{#if error}<p class="error" role="alert">{error}</p>{/if}

{#if !wk}
	{#if !loading}<p>No games loaded yet.</p>{/if}
{:else}
	<div class="weeks">
		<button onclick={() => step(-1)} disabled={wk.week <= 1} aria-label="Previous week">‹</button>
		<span>Week {wk.week}</span>
		<button onclick={() => step(1)} aria-label="Next week">›</button>
	</div>
	{#if loading}<p>Loading…</p>{/if}
	{#if m && !m.games.length}<p>No games this week.</p>{/if}
	{#if m}
		<p class="totals"><strong>You {m.myPoints}</strong> – <strong>{m.theirPoints} Them</strong></p>
		{#each m.games as g (g.game.id)}
			<article class="card">
				<header>
					<strong>{teamLabel(g.game.awayName, g.game.awayRank)} @ {teamLabel(g.game.homeName, g.game.homeRank)}</strong>
				</header>
				<p class="meta">
					{fmtKickoff(g.game.kickoffAt)}
					{#if g.game.homeScore !== null}· Final/live: {g.game.awayAbbr} {g.game.awayScore} – {g.game.homeAbbr} {g.game.homeScore}{/if}
				</p>
				<p>Me: {g.mine ? pickText(g.game, g.mine) : 'no pick'}</p>
				<p>
					Them:
					{#if !isLocked(g.game.kickoffAt, now)}<em>hidden until kickoff</em>
					{:else if g.theirs}{pickText(g.game, g.theirs)}
					{:else}no pick{/if}
				</p>
				{#if g.point}<p class="meta">Point: {g.point}</p>{/if}
			</article>
		{/each}
	{/if}
{/if}

{#if h}
	<h2>Season head-to-head</h2>
	<p>Points {h.pointsFor}–{h.pointsAgainst} · Weeks {h.weeksWon}W {h.weeksLost}L {h.weeksTied}T</p>
{/if}

<style>
	.weeks {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 0.5rem;
	}
	.weeks button {
		min-width: 44px;
		min-height: 44px;
	}
	.totals {
		font-size: 1.2rem;
		text-align: center;
	}
	.card {
		background: #fff;
		border: 1px solid #ddd;
		border-radius: 12px;
		padding: 0.75rem;
		margin-bottom: 0.75rem;
	}
	.card p {
		margin: 0.25rem 0;
	}
	.meta {
		color: #666;
		font-size: 0.85rem;
	}
</style>
