<script lang="ts">
	import { goto, invalidateAll } from '$app/navigation';
	import { gql } from '#lib/gql.js';

	let email = $state('');
	let password = $state('');
	let handle = $state('');
	let inviteCode = $state('');
	let error = $state('');

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		try {
			await gql(
				'mutation($email: String!, $password: String!, $handle: String!, $inviteCode: String!) { signUp(email: $email, password: $password, handle: $handle, inviteCode: $inviteCode) { user { id } } }',
				{ email, password, handle, inviteCode }
			);
			await invalidateAll();
			await goto('/');
		} catch (err) {
			error = (err as Error).message;
		}
	}
</script>

<h1>Sign up</h1>
<form onsubmit={submit}>
	<input type="email" placeholder="Email" autocomplete="email" required bind:value={email} />
	<input type="password" placeholder="Password" autocomplete="new-password" required bind:value={password} />
	<input placeholder="Handle" autocapitalize="none" required bind:value={handle} />
	<input placeholder="Invite code" required bind:value={inviteCode} />
	{#if error}<p class="error" role="alert">{error}</p>{/if}
	<button>Sign up</button>
</form>
<p>Have an account? <a href="/login">Log in</a></p>
