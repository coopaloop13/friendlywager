<script lang="ts">
	import { page } from '$app/state';
</script>

<h1>{page.status === 404 ? 'Out of bounds' : 'Flag on the play'}</h1>
<p class="error" role="alert">{page.status === 404 ? "That page doesn't exist." : page.error?.message}</p>
<p><a href="/">Back to this week</a></p>
