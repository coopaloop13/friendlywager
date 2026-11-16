<script lang="ts">
	import { SUPPORT } from '#lib/site.js';
</script>

<svelte:head><title>Privacy · Pick'ems</title></svelte:head>

<h1>Privacy</h1>
<p class="fine">Last updated 16 November 2026</p>

<p>Pick'ems keeps as little about you as it can. There are no ads, no trackers, and we never sell or share your data for marketing.</p>

<h2>What we keep</h2>
<ul>
	<li><strong>Your email address</strong>, used only to send you sign-in codes. Other players never see it.</li>
	<li><strong>Your handle</strong>, which anyone who knows it can use to send you a friend request.</li>
	<li><strong>Your picks</strong>. A friend can see your pick for a game only after that game kicks off. People who are not your friends never see your picks.</li>
	<li><strong>Your friendships</strong>, friend requests and the players you have blocked.</li>
	<li><strong>A sign-in code</strong>, stored scrambled for up to 10 minutes while you sign in.</li>
</ul>

<h2>On your device</h2>
<p>
	One cookie keeps you signed in for up to 30 days. Your browser also stores a copy of recent pages so they open
	quickly; logging out or deleting your account clears it. Neither is used to track you.
</p>

<h2>Who else handles it</h2>
<ul>
	<li><strong>Cloudflare</strong> hosts the app, sends the sign-in emails, and uses your IP address briefly to limit abuse.</li>
	<li><strong>Neon</strong> hosts the database.</li>
	<li><strong>Google Fonts</strong> and <strong>ESPN</strong> serve the fonts and team logos, so your browser contacts them when a page loads.</li>
</ul>

<h2>Deleting your data</h2>
<p>
	Settings → Delete account removes your account, every pick and every friendship immediately and for good. Database
	backups that still contain them expire within days. You can also ask us to do it at the address below.
</p>

<h2>Children</h2>
<p>Pick'ems is not for children under 13, and we do not knowingly keep data about them. If you believe a child has signed up, tell us and we will delete the account.</p>

<h2>Changes</h2>
<p>If this policy changes, the date above changes with it.</p>

<h2>Contact</h2>
<p><a href="mailto:{SUPPORT}">{SUPPORT}</a></p>

<style>
	h2 {
		margin-top: 1.5rem;
		font-size: 1.15rem;
	}
	.fine {
		font-size: 0.85rem;
		color: var(--muted);
	}
</style>
