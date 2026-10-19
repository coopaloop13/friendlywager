<script lang="ts">
	import { goto, invalidateAll } from '$app/navigation';
	import { gql } from '#lib/gql.js';

	let email = $state('');
	let password = $state('');
	let error = $state('');

	async function submit(e: SubmitEvent) {
		e.preventDefault();
		error = '';
		try {
			await gql(
				'mutation($email: String!, $password: String!) { logIn(email: $email, password: $password) { user { id } } }',
				{ email, password }
			);
			await invalidateAll();
			await goto('/');
		} catch (err) {
			error = (err as Error).message;
		}
	}
</script>

<h1>Log in</h1>
<form onsubmit={submit}>
	<label>Email
		<input type="email" autocomplete="email" required bind:value={email} />
	</label>
	<label>Password
		<input type="password" autocomplete="current-password" required bind:value={password} />
	</label>
	{#if error}<p class="error" role="alert">{error}</p>{/if}
	<button>Log in</button>
</form>
<p>No account? <a href="/signup">Sign up</a></p>
