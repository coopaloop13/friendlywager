<script lang="ts">
	// Team logo on a light chip (ESPN logos are drawn for light backgrounds); falls back to the abbreviation.
	let { logo, abbr, name, size = 28 }: { logo: string | null; abbr: string; name: string; size?: number } = $props();
	let broken = $state(false);
</script>

{#if logo && !broken}
	<img
		class="mark"
		src={logo}
		alt={name}
		title={name}
		width={size}
		height={size}
		loading="lazy"
		decoding="async"
		onerror={() => (broken = true)}
	/>
{:else}
	<abbr class="abbr" title={name}>{abbr}</abbr>
{/if}

<style>
	.mark {
		display: inline-block;
		vertical-align: middle;
		object-fit: contain;
		background: #fff;
		border-radius: 50%;
		padding: 3px;
		box-shadow: 0 0 0 1px rgb(0 0 0 / 0.12);
	}
	.abbr {
		text-decoration: none;
		font-family: var(--display);
		letter-spacing: 0.05em;
	}
</style>
