<script lang="ts">
	import { goto, invalidateAll } from '$app/navigation';
	import { gql, GqlError } from '#lib/gql.js';
	import { REQUEST_CODE, VERIFY_CODE, takeInvite } from '#lib/account.js';

	let step = $state<'email' | 'code' | 'handle'>('email');
	let email = $state('');
	let code = $state('');
	let handle = $state('');
	let error = $state('');
	let info = $state('');

	async function sendCode(e?: SubmitEvent) {
		e?.preventDefault();
		error = info = '';
		try {
			await gql(REQUEST_CODE, { email });
			code = '';
			info = step === 'email' ? '' : 'New code sent.';
			step = 'code';
		} catch (err) {
			error = (err as Error).message;
		}
	}

	async function verify(e: SubmitEvent) {
		e.preventDefault();
		error = info = '';
		try {
			await gql(VERIFY_CODE, { email, code, handle: step === 'handle' ? handle : null });
			await invalidateAll();
			const invite = takeInvite();
			await goto(invite ? `/add/${invite}` : '/');
		} catch (err) {
			// right code, new email: the same code finishes sign-up once a handle comes with it
			if (err instanceof GqlError && err.code === 'HANDLE_REQUIRED') step = 'handle';
			else error = (err as Error).message;
		}
	}
</script>

<svelte:head><title>Sign in · Pick'ems</title></svelte:head>

{#if step === 'email'}
	<h1>Sign in</h1>
	<p>Enter your email and we'll send a 6-digit code. New here? Same thing, no password needed.</p>
	<form onsubmit={sendCode}>
		<label>Email
			<input type="email" autocomplete="email" required bind:value={email} />
		</label>
		{#if error}<p class="error" role="alert">{error}</p>{/if}
		<button>Email me a code</button>
	</form>
{:else if step === 'code'}
	<h1>Check your email</h1>
	<p>We sent a 6-digit code to <strong>{email}</strong>. It expires in 10 minutes.</p>
	<form onsubmit={verify}>
		<label>Code
			<input inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{'{6}'}" maxlength="6" required bind:value={code} />
		</label>
		{#if error}<p class="error" role="alert">{error}</p>{/if}
		{#if info}<p role="status">{info}</p>{/if}
		<button>Sign in</button>
	</form>
	<p>
		<button type="button" class="link" onclick={() => sendCode()}>Send a new code</button>
		<button type="button" class="link" onclick={() => ((step = 'email'), (error = info = ''))}>Use a different email</button>
	</p>
{:else}
	<h1>Pick a handle</h1>
	<p>This is how friends find you. 3-20 characters: letters, numbers and underscores.</p>
	<form onsubmit={verify}>
		<label>Handle
			<input autocapitalize="none" autocorrect="off" autocomplete="username" spellcheck="false" minlength="3" maxlength="20" required bind:value={handle} />
		</label>
		{#if error}<p class="error" role="alert">{error}</p>{/if}
		<p class="fine">By creating an account you agree to the <a href="/terms">terms</a> and <a href="/privacy">privacy policy</a>, and confirm you are 13 or older.</p>
		<button>Create account</button>
	</form>
{/if}

<style>
	.fine {
		font-size: 0.85rem;
		color: var(--muted);
		margin: 0;
	}
	.link {
		background: none;
		border: none;
		box-shadow: none;
		padding: 0.6rem 0;
		margin-right: 1rem;
		min-height: 44px;
		color: var(--turf);
		text-transform: none;
		letter-spacing: 0;
		font-family: inherit;
		text-decoration: underline;
	}
</style>
