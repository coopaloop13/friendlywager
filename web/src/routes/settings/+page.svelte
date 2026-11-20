<script lang="ts">
	import { goto, invalidateAll } from '$app/navigation';
	import { fresh, gql, remember } from '#lib/gql.js';
	import { getLook, LOOKS, setLook, type Look } from '#lib/look.js';
	import { CHANGE_HANDLE, DELETE_ACCOUNT, forget, RESULT_PUSHES, SET_RESULT_PUSHES } from '#lib/account.js';
	import { signedOut } from '#lib/native.js';
	import { disablePush } from '#lib/push.js';
	import { reportHref, SUPPORT } from '#lib/site.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	let handle = $state('');
	let error = $state('');
	let info = $state('');
	let confirming = $state(false);
	let typed = $state('');
	let look = $state(getLook());
	let results = $state<boolean | null>(null); // unknown until the server answers

	const pushesKey = $derived(`pushes:${data.user?.id}`);

	$effect(() => {
		// only this switch changes it: show the last known setting at once, then confirm it
		fresh(
			pushesKey,
			() => gql<{ resultPushes: boolean }>(RESULT_PUSHES, undefined, fetch, { quiet: true }).then((d) => d.resultPushes),
			(on) => (results = on)
		).catch((e) => (error = e.message));
	});

	async function setResults(on: boolean) {
		error = info = '';
		try {
			await gql(SET_RESULT_PUSHES, { on }, fetch, { quiet: true });
			results = on;
			remember(pushesKey, on);
		} catch (err) {
			results = !on; // put the box back
			error = (err as Error).message;
		}
	}

	async function rename(e: SubmitEvent) {
		e.preventDefault();
		error = info = '';
		try {
			await gql(CHANGE_HANDLE, { handle: handle.trim().replace(/^@/, '') });
			handle = '';
			info = 'Handle changed.';
			await invalidateAll();
		} catch (err) {
			error = (err as Error).message;
		}
	}

	// both leave the account behind on this device
	async function leave(mutation: string) {
		error = info = '';
		try {
			await disablePush(); // while still signed in: the server only drops a device for its owner
			await gql(mutation);
			forget();
			await signedOut();
			await invalidateAll();
			await goto('/');
		} catch (err) {
			error = (err as Error).message;
		}
	}
</script>

<svelte:head><title>Settings · Pick'ems</title></svelte:head>

<h1>Settings</h1>
{#if error}<p class="error" role="alert">{error}</p>{/if}
{#if info}<p role="status">{info}</p>{/if}

<h2>Handle</h2>
<p>You are <strong>@{data.user?.handle}</strong>. Friends add you by this name.</p>
<form onsubmit={rename}>
	<label>New handle
		<input autocapitalize="none" autocorrect="off" autocomplete="off" spellcheck="false" minlength="3" maxlength="20" required bind:value={handle} />
	</label>
	<button>Change handle</button>
</form>

<h2>Look</h2>
<p>How the app looks on this device.</p>
<div class="looks" role="group" aria-label="Look">
	{#each Object.entries(LOOKS) as [id, name] (id)}
		<button aria-pressed={look === id} onclick={() => setLook((look = id as Look))}>{name}</button>
	{/each}
</div>

<h2>Notifications</h2>
<label class="check">
	<input
		type="checkbox"
		checked={results ?? true}
		disabled={results === null}
		onchange={(e) => setResults(e.currentTarget.checked)}
	/>
	<span>Tell me when a game ends and how I did against my friends</span>
</label>
<p class="fine">Sent to phones with the app installed. Reminders that picks are about to lock are not affected.</p>

<h2>Session</h2>
<button onclick={() => leave('mutation { logOut }')}>Log out</button>

<h2>Delete account</h2>
<p>
	This permanently deletes your account, every pick you have made and all your friendships. Your friends lose their
	history against you too. It cannot be undone.
</p>
{#if !confirming}
	<button class="danger" onclick={() => (confirming = true)}>Delete my account…</button>
{:else}
	<form onsubmit={(e) => (e.preventDefault(), leave(DELETE_ACCOUNT))}>
		<label>Type your handle to confirm
			<input autocapitalize="none" autocorrect="off" autocomplete="off" spellcheck="false" bind:value={typed} />
		</label>
		<button class="danger" disabled={typed.trim().replace(/^@/, '').toLowerCase() !== data.user?.handle}>
			Delete everything
		</button>
		<button type="button" onclick={() => ((confirming = false), (typed = ''))}>Keep my account</button>
	</form>
{/if}

<h2>About</h2>
<p>
	<a href="/terms">Terms</a> · <a href="/privacy">Privacy</a> · <a href={reportHref}>Report a user</a> ·
	<a href="mailto:{SUPPORT}">Contact</a>
</p>
<p class="fine">Pick'ems is free and for fun. No money, no prizes, no betting.</p>

<style>
	.fine {
		font-size: 0.85rem;
		color: var(--muted);
	}
	h2 {
		margin-top: 1.75rem;
	}
	.danger {
		background: var(--bad);
		color: var(--on-bad);
	}
	.check {
		flex-direction: row;
		align-items: center;
		gap: 0.6rem;
		min-height: 44px;
		font-weight: 400;
	}
	.check input {
		flex: none;
		width: 1.4rem;
		height: 1.4rem;
		padding: 0;
		accent-color: var(--sel);
	}
	.looks {
		display: flex;
		gap: 0.5rem;
	}
	.looks button {
		flex: 1;
		min-height: 44px;
		border-color: var(--rule);
		background: var(--surface);
		color: var(--muted);
		box-shadow: none;
	}
	.looks button[aria-pressed='true'] {
		border-color: var(--sel);
		background: var(--sel);
		color: var(--on-sel);
	}
</style>
