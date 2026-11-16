<!-- Shares the viewer's own invite link: the native share sheet where there is one, the clipboard otherwise. -->
<script lang="ts">
	import { NAME } from '#lib/site.js';

	let { handle }: { handle: string } = $props();
	let note = $state('');

	async function invite() {
		const url = `${location.origin}/add/${handle}`;
		const text = `Think you can out-pick me? Add me on ${NAME}.`;
		note = '';
		try {
			if (navigator.share) await navigator.share({ title: NAME, text, url });
			else {
				await navigator.clipboard.writeText(url);
				note = 'Link copied. Paste it to a friend.';
			}
		} catch (e) {
			// closing the share sheet is not an error
			if ((e as Error).name !== 'AbortError') note = `Your link: ${url}`;
		}
	}
</script>

<button type="button" onclick={invite}>Invite a friend</button>
{#if note}<p role="status">{note}</p>{/if}
