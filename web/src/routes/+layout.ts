import { redirect } from '@sveltejs/kit';
import { invalidateAll } from '$app/navigation';
import { forget, rememberInvite } from '#lib/account.js';
import { cached, gql, remember } from '#lib/gql.js';
import type { LayoutLoad } from './$types';

export const ssr = false;

export type User = { id: string; handle: string };

const ask = (f: typeof fetch) =>
	gql<{ me: User | null }>('{ me { id handle } }', undefined, f, { quiet: true }).then((d) => d.me);

export const load: LayoutLoad = async ({ fetch, url, untrack }) => {
	// quiet: preloads run this too, and an overlay mid-tap would swallow the click. Real navigations show via navigating.to.
	// A user kept on this device opens the app at once; the server is asked behind the page and has the last word.
	// This only decides what is drawn: every request is still checked against the session by the API.
	let me = cached<User>('me');
	if (me) {
		const kept = me;
		void ask(fetch).then(
			(now) => {
				if (now?.id === kept.id && now.handle === kept.handle) return;
				forget(); // signed out, renamed or someone else: nothing kept for the old answer may stay
				if (now) remember('me', now);
				return invalidateAll(); // reruns this load, which now starts from the server's answer
			},
			() => {} // API down or still starting: the kept pages are better than an error screen
		);
	} else {
		try {
			me = await ask(fetch);
		} catch {
			// API down or still starting: a throw here would bypass the layout and show SvelteKit's bare error page.
			return { user: null, unavailable: true };
		}
		if (me) remember('me', me);
	}
	// untracked: otherwise every tab switch reruns this load and refetches `me` before the page can swap.
	// Log in/out call invalidateAll(), which reruns it with the current url.
	const path = untrack(() => url.pathname);
	if (path === '/signup') redirect(307, '/login'); // old links; the login page signs new people up now
	const isAuthPage = path === '/login';
	if (!me && path.startsWith('/add/')) {
		rememberInvite(decodeURIComponent(path.slice(5)));
		redirect(307, '/login'); // the login page sends them back to the invite once they're in
	}
	if (!me && !isAuthPage && !['/', '/terms', '/privacy'].includes(path)) redirect(307, '/');
	if (me && isAuthPage) redirect(307, '/');
	return { user: me, unavailable: false };
};
