<script lang="ts">
	import { gql, GqlError } from '#lib/gql.js';
	import { fmtKickoff, saveAction, teamLabel, type GameView, type PickView } from '#lib/picks.js';

	let { game, pick }: { game: GameView; pick: PickView | null } = $props();

	// svelte-ignore state_referenced_locally
	let home = $state(pick?.home?.toString() ?? '');
	// svelte-ignore state_referenced_locally
	let away = $state(pick?.away?.toString() ?? '');
	let status = $state('');
	let failed = $state(false);

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
				try {
					if (act.kind === 'error') [status, failed] = [act.message, true];
					else if (act.kind === 'delete') {
						await gql('mutation($id: ID!) { deletePick(gameId: $id) }', { id: game.id });
						[pick, status, failed] = [null, 'Cleared', false];
					} else if (act.kind === 'save') {
						await gql(
							'mutation($id: ID!, $h: Int!, $a: Int!) { savePick(gameId: $id, home: $h, away: $a) { home away } }',
							{ id: game.id, h: act.home, a: act.away }
						);
						[pick, status, failed] = [{ home: act.home, away: act.away }, 'Saved', false];
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
		<span class="badge" class:locked={game.locked}>{game.locked ? 'Locked' : 'Open'}</span>
	</header>
	<div class="teams">
		<div class="team">
			<span>{teamLabel(game.awayName, game.awayRank)}</span>
			{#if hasScore}<strong>{game.awayScore}</strong>{/if}
		</div>
		<div class="team">
			<span>{teamLabel(game.homeName, game.homeRank)}</span>
			{#if hasScore}<strong>{game.homeScore}</strong>{/if}
		</div>
	</div>
	{#if hasScore}<p class="meta">{game.status}</p>{/if}
	{#if game.spread}<p class="meta">Spread: {game.spread}</p>{/if}

	{#if game.locked}
		<p class="pick">
			Your pick:
			{#if pick}{game.awayAbbr} {pick.away} – {game.homeAbbr} {pick.home}{:else}none{/if}
		</p>
	{:else}
		<div class="inputs">
			<label>
				<span class="sr">{game.awayAbbr} score</span>
				<span aria-hidden="true">{game.awayAbbr}</span>
				<input inputmode="numeric" pattern="[0-9]*" bind:value={away} onblur={save} />
			</label>
			<label>
				<span class="sr">{game.homeAbbr} score</span>
				<span aria-hidden="true">{game.homeAbbr}</span>
				<input inputmode="numeric" pattern="[0-9]*" bind:value={home} onblur={save} />
			</label>
		</div>
		<p class:error={failed} class="status" role="status">{status}</p>
	{/if}
</article>

<style>
	.card {
		background: #fff;
		border: 1px solid #ddd;
		border-radius: 12px;
		padding: 0.75rem;
		margin-bottom: 0.75rem;
	}
	header,
	.team {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}
	.when,
	.meta {
		color: #666;
		font-size: 0.85rem;
		margin: 0.25rem 0;
	}
	.badge {
		font-size: 0.75rem;
		padding: 0.1rem 0.5rem;
		border-radius: 99px;
		background: #dff5e1;
		color: #1b6b2a;
	}
	.badge.locked {
		background: #eee;
		color: #555;
	}
	.inputs {
		display: flex;
		gap: 0.75rem;
		margin-top: 0.5rem;
	}
	.inputs label {
		flex: 1;
		align-items: center;
		text-align: center;
	}
	input {
		width: 100%;
		box-sizing: border-box;
		min-height: 44px;
		text-align: center;
		font-size: 1.1rem;
	}
	.status {
		min-height: 1.5rem;
		margin: 0.25rem 0 0;
		font-size: 0.85rem;
	}
	.sr {
		position: absolute;
		width: 1px;
		height: 1px;
		overflow: hidden;
		clip-path: inset(50%);
	}
</style>
