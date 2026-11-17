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
			<span class="name"><span aria-hidden="true"><TeamMark logo={game.awayLogo} abbr="" name={game.awayName} /></span>{teamLabel(game.awayName, game.awayRank)}{#if game.awayRecord}<small class="rec">({game.awayRecord})</small>{/if}</span>
			{#if hasScore}<strong>{game.awayScore}</strong>{/if}
		</div>
		<div class="team">
			<span class="name"><span aria-hidden="true"><TeamMark logo={game.homeLogo} abbr="" name={game.homeName} /></span>{teamLabel(game.homeName, game.homeRank)}{#if game.homeRecord}<small class="rec">({game.homeRecord})</small>{/if}</span>
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
		background: var(--surface);
		border: 2px solid var(--line);
		border-radius: var(--radius);
		padding: 0.9rem;
		margin-bottom: 1rem;
		box-shadow: 0 4px 0 var(--line);
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
	.rec {
		color: var(--muted);
		font-weight: 400;
		font-size: 0.8rem;
		margin-left: -0.2rem;
	}
	.teams {
		margin: 0.4rem 0;
		font-weight: 600;
		font-size: 1.05rem;
	}
	.team strong {
		font-family: var(--num);
		font-variant-numeric: tabular-nums;
		font-size: 1.25rem;
		font-weight: 800;
		min-width: 2.5rem;
		text-align: center;
		background: var(--tile);
		color: var(--on-tile);
		border-radius: var(--radius-s);
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
		font-weight: 700;
		text-transform: var(--caps);
		padding: 0.1rem 0.6rem;
		border-radius: var(--pill);
		background: var(--accent);
		color: var(--on-accent);
	}
	.badge.locked {
		background: var(--rule);
		color: var(--ink);
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
		margin-top: 0.6rem;
	}
	.inputs label {
		flex: 1;
		min-width: 0;
		flex-direction: row;
		align-items: center;
		gap: 0.5rem;
		font-family: var(--display);
	}
	input {
		flex: 1;
		min-width: 0;
		width: 100%;
		box-sizing: border-box;
		min-height: 48px;
		text-align: center;
		font-family: var(--num);
		font-size: 1.4rem;
		font-weight: 800;
		background: var(--well);
		color: var(--on-tile);
		border-color: var(--line);
	}
	.status {
		min-height: 1.5rem;
		margin: 0.25rem 0 0;
		font-size: 0.85rem;
		color: var(--good);
		font-weight: 600;
	}
	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
	}

	/* Section 112: the card is a ticket. The kickoff time becomes the stub, torn off along a perforation. */
	:global(:root[data-look='s112']) .card {
		position: relative;
		display: grid;
		grid-template-columns: 4.25rem minmax(0, 1fr);
		column-gap: 0.75rem;
		padding-left: 0;
	}
	:global(:root[data-look='s112']) .card > * {
		grid-column: 2;
	}
	:global(:root[data-look='s112']) .card > header {
		display: contents;
	}
	:global(:root[data-look='s112']) .when {
		grid-column: 1;
		grid-row: 1 / span 8;
		display: grid;
		place-items: center;
		margin: -0.9rem 0;
		padding: 0 0.4rem;
		border-right: 2px dashed var(--ground);
		font: 600 0.68rem/1.5 var(--num);
		text-transform: uppercase;
		text-align: center;
	}
	:global(:root[data-look='s112']) .badge {
		grid-column: 2;
		justify-self: end;
	}
	:global(:root[data-look='s112']) .card::before,
	:global(:root[data-look='s112']) .card::after {
		content: '';
		position: absolute;
		left: calc(4.25rem - 7px);
		width: 16px;
		height: 16px;
		border-radius: 50%;
		background: var(--ground);
	}
	:global(:root[data-look='s112']) .card::before {
		top: -10px;
	}
	:global(:root[data-look='s112']) .card::after {
		bottom: -10px;
	}
</style>
