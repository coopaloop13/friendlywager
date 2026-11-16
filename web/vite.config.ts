import adapter from '@sveltejs/adapter-cloudflare';
import adapterStatic from '@sveltejs/adapter-static';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) =>
					filename.split(/[/\\]/).includes('node_modules') ? undefined : true
			},

			// BUILD_TARGET=app: plain files for the Capacitor shell (see capacitor.config.ts). Default: the web Worker.
			adapter: process.env.BUILD_TARGET === 'app' ? adapterStatic({ fallback: 'index.html' }) : adapter()
		})
	]
});
