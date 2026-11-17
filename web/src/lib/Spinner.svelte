<!-- Loading ring, used by the loading overlay. Keep in sync with the boot copy in app.html. -->
<span class="ring" aria-hidden="true"></span>

<style>
	.ring {
		display: inline-block;
		width: 44px;
		height: 44px;
		border: 5px solid var(--rule);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: fw-spin 0.9s linear infinite;
	}
	@keyframes fw-spin {
		to {
			transform: rotate(360deg);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.ring {
			animation-duration: 3s;
		}
	}
</style>
