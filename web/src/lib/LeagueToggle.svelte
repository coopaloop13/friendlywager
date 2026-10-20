<script lang="ts">
	let { league }: { league: 'NFL' | 'CFB' } = $props();
</script>

<nav class="toggle" aria-label="League">
	<a href="?league=nfl" aria-current={league === 'NFL' ? 'true' : undefined}>NFL</a>
	<a href="?league=cfb" aria-current={league === 'CFB' ? 'true' : undefined}>CFB</a>
</nav>

<style>
	.toggle {
		display: flex;
		margin-bottom: 1rem;
		background: #111;
		border-radius: 12px;
		padding: 4px;
	}
	a {
		flex: 1;
		min-height: 44px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 9px;
		text-decoration: none;
		color: #bbb;
		font-family: var(--display);
		letter-spacing: 0.08em;
	}
	a[aria-current] {
		background: var(--gold);
		color: var(--ink);
	}
</style>
