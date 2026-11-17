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
		background: var(--well);
		border-radius: var(--pill);
		padding: 4px;
	}
	a {
		flex: 1;
		min-height: 44px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--pill);
		text-decoration: none;
		color: var(--muted);
		font-family: var(--display);
		font-weight: 700;
	}
	a[aria-current] {
		background: var(--sel);
		color: var(--on-sel);
	}
</style>
