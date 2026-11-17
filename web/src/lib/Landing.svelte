<svelte:head><title>Pick'ems: Box Score Picks</title></svelte:head>

<section class="hero">
	<p class="kicker">NFL · College Football</p>
	<h1>Call the score.<br />Beat your friends.</h1>
	<p class="lede">Weekly pick'em for bragging rights. No money, just glory.</p>
	<div class="cta">
		<a class="btn primary" href="/login">Get started</a>
	</div>
	<p class="invite">Sign in with your email. No password to remember.</p>
</section>

<ol class="steps">
	<li>
		<span aria-hidden="true">1</span>
		<div><strong>Pick the final score</strong> for every game on the week's slate, before kickoff.</div>
	</li>
	<li>
		<span aria-hidden="true">2</span>
		<div><strong>Go head to head</strong> with each friend. Pick the winner and get closest to the score to take the point.</div>
	</li>
	<li>
		<span aria-hidden="true">3</span>
		<div><strong>Climb the leaderboard</strong>. Every week's picks and results are saved all season.</div>
	</li>
</ol>

<footer>
	<p>Free and for fun. No money, no prizes, no betting.</p>
	<p><a href="/terms">Terms</a> · <a href="/privacy">Privacy</a></p>
</footer>

<style>
	footer {
		margin-top: 1.5rem;
		text-align: center;
		font-size: 0.85rem;
		color: var(--muted);
	}
	footer p {
		margin: 0.25rem 0;
	}
	.hero {
		margin: -1rem -1rem 0;
		padding: 2.25rem 1.25rem 2rem;
		color: var(--on-inv);
		background: var(--inv);
	}
	.kicker {
		margin: 0;
		font-family: var(--display);
		font-weight: 700;
		text-transform: var(--caps);
		color: var(--accent);
	}
	h1 {
		color: var(--on-inv);
		font-size: 2.4rem;
		line-height: 1.05;
	}
	.lede {
		margin: 0 0 1.25rem;
		font-size: 1.05rem;
	}
	.cta {
		display: flex;
	}
	.btn {
		flex: 1;
		min-height: 50px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: var(--pill);
		background: var(--accent);
		color: var(--on-accent);
		text-decoration: none;
		font-family: var(--display);
		font-size: 1.1rem;
		font-weight: 800;
		text-transform: var(--caps);
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
		background: var(--surface);
		border: 2px solid var(--line);
		border-radius: var(--radius);
	}
	.steps span {
		flex: none;
		width: 1.8rem;
		height: 1.8rem;
		display: grid;
		place-items: center;
		border-radius: var(--pill);
		background: var(--accent);
		color: var(--on-accent);
		font: 800 1rem var(--display);
	}
	.steps strong {
		font-family: var(--display);
	}
</style>
