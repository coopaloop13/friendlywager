<script lang="ts">
	import { gql } from '#lib/gql.js';

	type U = { id: string; handle: string };
	let friends = $state<U[]>([]);
	let requests = $state<{ id: string; from: U }[]>([]);
	let sent = $state<{ id: string; to: U }[]>([]);
	let handle = $state('');
	let error = $state('');
	let info = $state('');

	async function load() {
		const d = await gql<{ friends: U[]; pendingRequests: typeof requests; sentRequests: typeof sent }>(
			'{ friends { id handle } pendingRequests { id from { id handle } } sentRequests { id to { id handle } } }'
		);
		friends = d.friends;
		requests = d.pendingRequests;
		sent = d.sentRequests;
	}

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
	<p>No friends yet. Add someone by handle.</p>
{/if}

<style>
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
		border-bottom: 2px dashed var(--line);
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
		background: var(--chalk);
		border-color: var(--line);
		box-shadow: 0 3px 0 var(--line);
		color: var(--muted);
	}
</style>
