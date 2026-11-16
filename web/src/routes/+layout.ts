import { redirect } from '@sveltejs/kit';
import { gql } from '#lib/gql.js';
import type { LayoutLoad } from './$types';

export const ssr = false;

export type User = { id: string; handle: string };

export const load: LayoutLoad = async ({ fetch, url, untrack }) => {
	// quiet: preloads run this too, and an overlay mid-tap would swallow the click. Real navigations show via navigating.to.
	let me: User | null;
	try {
		({ me } = await gql<{ me: User | null }>('{ me { id handle } }', undefined, fetch, { quiet: true }));
	} catch {
		// API down or still starting: a throw here would bypass the layout and show SvelteKit's bare error page.
		return { user: null, unavailable: true };
	}
	// untracked: otherwise every tab switch reruns this load and refetches `me` before the page can swap.
	// Log in/out call invalidateAll(), which reruns it with the current url.
	const path = untrack(() => url.pathname);
	if (path === '/signup') redirect(307, '/login'); // old links; the login page signs new people up now
	const isAuthPage = path === '/login';
	if (!me && !isAuthPage && path !== '/') redirect(307, '/');
	if (me && isAuthPage) redirect(307, '/');
	return { user: me, unavailable: false };
};
