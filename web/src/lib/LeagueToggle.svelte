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
		gap: 0.5rem;
		margin-bottom: 1rem;
	}
	a {
		flex: 1;
		min-height: 44px;
		display: flex;
		align-items: center;
		justify-content: center;
		border: 1px solid #1a5fd0;
		border-radius: 8px;
		text-decoration: none;
		color: #1a5fd0;
	}
	a[aria-current] {
		background: #1a5fd0;
		color: #fff;
	}
</style>
