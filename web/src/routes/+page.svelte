<script lang="ts">
	import { goto, invalidateAll } from '$app/navigation';
	import { gql } from '#lib/gql.js';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	async function logOut() {
		await gql('mutation { logOut }');
		await invalidateAll();
		await goto('/login');
	}
</script>

<h1>This week</h1>
<p>Signed in as @{data.user?.handle}</p>
<button onclick={logOut}>Log out</button>
