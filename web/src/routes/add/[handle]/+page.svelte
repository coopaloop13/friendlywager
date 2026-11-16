<script lang="ts">
	import { page } from '$app/state';
	import { gql } from '#lib/gql.js';
	import Invite from '#lib/Invite.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const handle = $derived((page.params.handle ?? '').toLowerCase());
	let error = $state('');
	let sent = $state(false);

	// A tap, never automatic: a link alone must not be able to make someone send a friend request.
	async function add() {
		error = '';
		try {
			await gql('mutation($h: String!) { sendFriendRequest(handle: $h) }', { h: handle });
			sent = true;
		} catch (e) {
			error = (e as Error).message;
		}
	}
</script>

<svelte:head><title>Add @{handle} · Pick'ems</title></svelte:head>

{#if handle === data.user?.handle}
	<h1>Your invite link</h1>
	<p>This link is yours. Send it to a friend and they can add you in one tap.</p>
	<Invite {handle} />
{:else if sent}
	<h1>Request sent</h1>
	<p role="status">@{handle} will see it on their friends page. Once they accept, you go head to head every week.</p>
	<p><a href="/">Make this week's picks</a></p>
{:else}
	<h1>Add @{handle}?</h1>
	<p>@{handle} invited you to go head to head on picks.</p>
	{#if error}<p class="error" role="alert">{error}</p>{/if}
	<button onclick={add}>Send friend request</button>
	<p><a href="/">Not now</a></p>
{/if}
