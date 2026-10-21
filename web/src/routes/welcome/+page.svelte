<script lang="ts">
	import Football from '#lib/Football.svelte';
</script>

<svelte:head><title>Friendly Wager · Pick'em with friends</title></svelte:head>

<section class="hero">
	<div class="ball"><Football /></div>
	<p class="kicker">NFL · College Football</p>
	<h1>Call the score.<br />Beat your friends.</h1>
	<p class="lede">Weekly pick'em for bragging rights. No money, just glory.</p>
	<div class="cta">
		<a class="btn primary" href="/signup">Sign up</a>
		<a class="btn" href="/login">Log in</a>
	</div>
	<p class="invite">Invite code required to sign up.</p>
</section>

<ol class="steps">
	<li>
		<span aria-hidden="true">✍️</span>
		<div><strong>Pick the final score</strong> for every game on the week's slate, before kickoff.</div>
	</li>
	<li>
		<span aria-hidden="true">🤝</span>
		<div><strong>Go head to head</strong> with each friend. Pick the winner and get closest to the score to take the point.</div>
	</li>
	<li>
		<span aria-hidden="true">🏆</span>
		<div><strong>Climb the leaderboard</strong>. Every week's picks and results are saved all season.</div>
	</li>
</ol>

<style>
	.hero {
		margin: -1rem -1rem 0;
		padding: 2rem 1.25rem 1.75rem;
		text-align: center;
		color: #fff;
		background: var(--turf) repeating-linear-gradient(0deg, transparent 0 46px, rgb(255 255 255 / 0.12) 46px 48px);
		border-bottom: 4px solid var(--gold);
	}
	.ball :global(.ball) {
		animation-duration: 6s;
	}
	.kicker {
		margin: 0.5rem 0 0;
		font-family: var(--display);
		text-transform: uppercase;
		letter-spacing: 0.12em;
		color: var(--gold);
	}
	h1 {
		display: block;
		border: 0;
		color: #fff;
		font-family: var(--varsity);
		font-size: 2rem;
		line-height: 1.15;
		text-transform: none;
		text-shadow: 0 3px 0 rgb(0 0 0 / 0.35);
	}
	.lede {
		margin: 0 0 1.25rem;
		font-size: 1.05rem;
	}
	.cta {
		display: flex;
		gap: 0.75rem;
	}
	.btn {
		flex: 1;
		min-height: 48px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 10px;
		border: 2px solid #fff;
		color: #fff;
		text-decoration: none;
		font-family: var(--display);
		font-size: 1.1rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.btn.primary {
		background: var(--gold);
		border-color: var(--gold-dark);
		color: var(--ink);
		box-shadow: 0 3px 0 var(--gold-dark);
	}
	.btn:active {
		transform: translateY(2px);
	}
	.invite {
		margin: 0.75rem 0 0;
		font-size: 0.85rem;
		opacity: 0.85;
	}
	.steps {
		list-style: none;
		padding: 0;
		margin: 1.5rem 0 0;
		display: grid;
		gap: 0.75rem;
	}
	.steps li {
		display: flex;
		gap: 0.75rem;
		align-items: flex-start;
		padding: 0.9rem 1rem;
		background: var(--chalk);
		border: 2px solid var(--line);
		border-left: 6px solid var(--turf);
		border-radius: 12px;
	}
	.steps span {
		font-size: 1.5rem;
		line-height: 1.2;
	}
	.steps strong {
		font-family: var(--display);
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--turf-dark);
	}
</style>
