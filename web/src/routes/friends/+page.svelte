<script lang="ts">
	import { fresh, gql } from '#lib/gql.js';
	import Invite from '#lib/Invite.svelte';
	import { reportHref } from '#lib/site.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	type U = { id: string; handle: string };
	let friends = $state<U[]>([]);
	let requests = $state<{ id: string; from: U }[]>([]);
	let sent = $state<{ id: string; to: U }[]>([]);
	let handle = $state('');
	let error = $state('');
	let info = $state('');

	// the lists only change when someone acts on them: show the last copy at once, refresh quietly
	const load = () =>
		fresh<{ friends: U[]; pendingRequests: typeof requests; sentRequests: typeof sent }>(
			`friends:${data.user?.id}`,
			(quiet) =>
				gql(
					'{ friends { id handle } pendingRequests { id from { id handle } } sentRequests { id to { id handle } } }',
					undefined,
					fetch,
					{ quiet }
				),
			(d) => {
				friends = d.friends;
				requests = d.pendingRequests;
				sent = d.sentRequests;
			}
		);

	// run an action, then reload; surface errors inline
	async function act(fn: () => Promise<unknown>, ok = '') {
		error = '';
		info = '';
		try {
			await fn();
			info = ok;
			await load();
		} catch (e) {
			error = (e as Error).message;
		}
	}

	const add = (e: SubmitEvent) => {
		e.preventDefault();
		const h = handle.trim().replace(/^@/, '').toLowerCase();
		return act(async () => {
			await gql('mutation($h: String!) { sendFriendRequest(handle: $h) }', { h });
			handle = '';
		}, 'Request sent');
	};
	const respond = (id: string, accept: boolean) =>
		act(() =>
			gql('mutation($id: ID!, $a: Boolean!) { respondToFriendRequest(id: $id, accept: $a) }', {
				id,
				a: accept
			})
		);
	const remove = (f: U) => {
		if (!confirm(`Remove @${f.handle}?`)) return;
		return act(() =>
			gql('mutation($id: ID!) { removeFriend(userId: $id) }', { id: f.id })
		);
	};

	const block = (u: U) => {
		if (!confirm(`Block @${u.handle}? They won't be told, and their requests will stop reaching you.`)) return;
		return act(() => gql('mutation($id: ID!) { blockUser(userId: $id) }', { id: u.id }), `Blocked @${u.handle}`);
	};

	$effect(() => {
		load().catch((e) => (error = e.message));
	});
</script>

<svelte:head><title>Friends · Pick'ems</title></svelte:head>

<h1>Friends</h1>
<form onsubmit={add}>
	<label>Add by handle
		<input autocapitalize="none" autocomplete="off" required bind:value={handle} />
	</label>
	<button>Send request</button>
</form>
{#if error}<p class="error" role="alert">{error}</p>{/if}
{#if info}<p role="status">{info}</p>{/if}

{#if requests.length}
	<h2>Requests</h2>
	<ul>
		{#each requests as r (r.id)}
			<li>
				<span>@{r.from.handle}</span>
				<span class="btns">
					<button onclick={() => respond(r.id, true)}>Accept</button>
					<button class="sec" onclick={() => respond(r.id, false)}>Decline</button>
					<button class="sec" onclick={() => block(r.from)}>Block</button>
				</span>
			</li>
		{/each}
	</ul>
{/if}

{#if sent.length}
	<h2>Sent</h2>
	<ul>
		{#each sent as s (s.id)}
			<li>
				<span>@{s.to.handle}</span>
				<button class="sec" onclick={() => respond(s.id, false)}>Cancel</button>
			</li>
		{/each}
	</ul>
{/if}

<h2>Your friends</h2>
{#if friends.length}
	<ul>
		{#each friends as f (f.id)}
			<li>
				<a href="/matchup/{f.id}">@{f.handle}</a>
				<span class="btns">
					<button class="sec" onclick={() => remove(f)}>Remove</button>
					<button class="sec" onclick={() => block(f)}>Block</button>
				</span>
			</li>
		{/each}
	</ul>
{:else}
	<p>No friends yet. Add someone by handle, or send them your link.</p>
{/if}

{#if data.user}
	<h2>Invite</h2>
	<p>Your link adds you in one tap, even if they haven't signed up yet.</p>
	<Invite handle={data.user.handle} />
{/if}

<p class="report">Someone being a problem? Block them above, or <a href={reportHref}>report them</a>.</p>

<style>
	.report {
		margin-top: 2rem;
		font-size: 0.85rem;
		color: var(--muted);
	}
	ul {
		list-style: none;
		padding: 0;
	}
	li {
		display: flex;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem;
		min-height: 44px;
		border-bottom: 2px dotted var(--rule);
	}
	li a {
		flex: 1;
		line-height: 44px;
	}
	.btns {
		display: flex;
		gap: 0.5rem;
	}
	button {
		min-height: 44px;
	}
	.sec {
		background: var(--surface);
		border-color: var(--rule);
		box-shadow: 0 3px 0 var(--rule);
		color: var(--muted);
	}
</style>
