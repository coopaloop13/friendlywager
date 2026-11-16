<script lang="ts">
	import { goto, invalidateAll } from '$app/navigation';
	import { gql } from '#lib/gql.js';
	import { CHANGE_HANDLE, DELETE_ACCOUNT, forget } from '#lib/account.js';
	import { reportHref, SUPPORT } from '#lib/site.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	let handle = $state('');
	let error = $state('');
	let info = $state('');
	let confirming = $state(false);
	let typed = $state('');

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
			await gql(mutation);
			forget();
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
		background: var(--red);
		border-color: #8f0b20;
		box-shadow: 0 3px 0 #8f0b20;
		color: #fff;
	}
</style>
