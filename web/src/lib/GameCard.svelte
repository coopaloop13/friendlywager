<script lang="ts">
	import { onMount } from 'svelte';
	import { gql, GqlError } from '#lib/gql.js';
	import TeamMark from '#lib/TeamMark.svelte';
	import { fmtKickoff, lockedNow, saveAction, teamLabel, type GameView, type PickView } from '#lib/picks.js';

	let { game, pick }: { game: GameView; pick: PickView | null } = $props();

	// svelte-ignore state_referenced_locally
	let home = $state(pick?.home?.toString() ?? '');
	// svelte-ignore state_referenced_locally
	let away = $state(pick?.away?.toString() ?? '');
	let status = $state('');
	let failed = $state(false);

	let now = $state(new Date());
	onMount(() => {
		const t = setInterval(() => (now = new Date()), 30_000);
		return () => clearInterval(t);
	});
	const locked = $derived(lockedNow(game, now));

	const hasScore = $derived(game.homeScore !== null && game.awayScore !== null);

	let busy = false;
	let dirty = false;

	async function save() {
		if (busy) return (dirty = true); // re-run once the in-flight save finishes
		busy = true;
		try {
			do {
				dirty = false;
				const act = saveAction(home, away, pick);
				if (act.kind === 'delete' || act.kind === 'save') [status, failed] = ['Saving…', false];
				try {
					if (act.kind === 'none') {
						if (act.clear) [status, failed] = ['', false];
					} else if (act.kind === 'error') [status, failed] = [act.message, true];
					else if (act.kind === 'delete') {
						await gql('mutation($id: ID!) { deletePick(gameId: $id) }', { id: game.id }, fetch, { quiet: true });
						[pick, status, failed] = [null, 'Cleared', false];
					} else if (act.kind === 'save') {
						await gql(
							'mutation($id: ID!, $h: Int!, $a: Int!) { savePick(gameId: $id, home: $h, away: $a) { home away } }',
							{ id: game.id, h: act.home, a: act.away },
							fetch,
							{ quiet: true }
						);
						[pick, status, failed] = [{ home: act.home, away: act.away }, 'Saved ✓', false];
					}
				} catch (e) {
					failed = true;
					status =
						e instanceof GqlError && e.code === 'LOCKED'
							? 'Locked — game has started'
							: (e as Error).message;
				}
			} while (dirty);
		} finally {
			busy = false;
		}
	}
</script>

<article class="card">
	<header>
		<span class="when">{fmtKickoff(game.kickoffAt)}</span>
		<span class="badge" class:locked={locked}>{locked ? 'Locked' : 'Open'}</span>
	</header>
	<div class="teams">
		<div class="team">
			<span class="name"><span aria-hidden="true"><TeamMark logo={game.awayLogo} abbr="" name={game.awayName} /></span>{teamLabel(game.awayName, game.awayRank)}</span>
			{#if hasScore}<strong>{game.awayScore}</strong>{/if}
		</div>
		<div class="team">
			<span class="name"><span aria-hidden="true"><TeamMark logo={game.homeLogo} abbr="" name={game.homeName} /></span>{teamLabel(game.homeName, game.homeRank)}</span>
			{#if hasScore}<strong>{game.homeScore}</strong>{/if}
		</div>
	</div>
	{#if hasScore}<p class="meta">{game.status}</p>{/if}
	{#if game.spread}<p class="meta">Spread: {game.spread}</p>{/if}

	{#if locked}
		<p class="pick">
			Your pick:
			{#if pick}
				<TeamMark logo={game.awayLogo} abbr={game.awayAbbr} name={game.awayName} size={22} />
				{pick.away} –
				<TeamMark logo={game.homeLogo} abbr={game.homeAbbr} name={game.homeName} size={22} />
				{pick.home}
			{:else}none{/if}
		</p>
	{:else}
		<div class="inputs">
			<label>
				<span class="sr">{game.awayName} score</span>
				<span aria-hidden="true"><TeamMark logo={game.awayLogo} abbr={game.awayAbbr} name={game.awayName} size={34} /></span>
				<input inputmode="numeric" pattern="[0-9]*" bind:value={away} onblur={save} />
			</label>
			<label>
				<span class="sr">{game.homeName} score</span>
				<span aria-hidden="true"><TeamMark logo={game.homeLogo} abbr={game.homeAbbr} name={game.homeName} size={34} /></span>
				<input inputmode="numeric" pattern="[0-9]*" bind:value={home} onblur={save} />
			</label>
		</div>
		<p class:error={failed} class="status" role="status">{status}</p>
	{/if}
</article>

<style>
	.card {
		background: var(--chalk);
		border: 2px solid var(--line);
		border-left: 6px solid var(--turf);
		border-radius: 14px;
		padding: 0.75rem;
		margin-bottom: 0.9rem;
		box-shadow: 0 2px 6px rgb(0 0 0 / 0.06);
	}
	.card:has(.badge.locked) {
		border-left-color: var(--muted);
	}
	header,
	.team {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.name {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.teams {
		margin: 0.4rem 0;
		font-weight: 600;
		font-size: 1.05rem;
	}
	.team strong {
		font-family: var(--display);
		font-size: 1.3rem;
		min-width: 2.5rem;
		text-align: center;
		background: #111;
		color: var(--gold);
		border-radius: 6px;
		padding: 0 0.4rem;
		margin: 0.15rem 0;
	}
	.when,
	.meta {
		color: var(--muted);
		font-size: 0.85rem;
		margin: 0.25rem 0;
	}
	.badge {
		font-family: var(--display);
		font-size: 0.75rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		padding: 0.1rem 0.6rem;
		border-radius: 99px;
		background: var(--turf);
		color: #fff;
	}
	.badge.locked {
		background: var(--red);
	}
	.pick {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		margin: 0.4rem 0 0;
		font-weight: 600;
	}
	.inputs {
		display: flex;
		gap: 0.75rem;
		margin-top: 0.5rem;
		padding: 0.5rem;
		background: #111;
		border-radius: 10px;
	}
	.inputs label {
		flex: 1;
		align-items: center;
		text-align: center;
		color: #ddd;
		font-family: var(--display);
		letter-spacing: 0.05em;
	}
	input {
		width: 100%;
		box-sizing: border-box;
		min-height: 48px;
		text-align: center;
		font-family: var(--display);
		font-size: 1.5rem;
		font-weight: 700;
		background: #222;
		color: var(--gold);
		border-color: #333;
	}
	.status {
		min-height: 1.5rem;
		margin: 0.25rem 0 0;
		font-size: 0.85rem;
		color: var(--turf);
		font-weight: 600;
	}
	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
	}
</style>
