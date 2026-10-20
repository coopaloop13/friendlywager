<!-- Spinning football, used by the loading overlay. Keep in sync with the boot copy in app.html. -->
<svg class="ball" viewBox="0 0 64 40" aria-hidden="true">
	<ellipse cx="32" cy="20" rx="30" ry="18" fill="#8b4a1f" stroke="#5a2e10" stroke-width="2" />
	<path d="M12 8v24M52 8v24" stroke="#fff" stroke-width="3" />
	<path d="M20 20h24M24 16v8M29 16v8M34 16v8M39 16v8" stroke="#fff" stroke-width="2" stroke-linecap="round" />
</svg>

<style>
	.ball {
		width: 72px;
		animation: fw-spin 0.9s linear infinite;
	}
	@keyframes fw-spin {
		to {
			transform: rotate(360deg);
		}
	}
	@media (prefers-reduced-motion: reduce) {
		.ball {
			animation-duration: 3s;
		}
	}
</style>
