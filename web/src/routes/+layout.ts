import { redirect } from '@sveltejs/kit';
import { gql } from '#lib/gql.js';
import type { LayoutLoad } from './$types';

export const ssr = false;

export type User = { id: string; handle: string };

export const load: LayoutLoad = async ({ fetch, url }) => {
	// quiet: preloads run this too, and an overlay mid-tap would swallow the click. Real navigations show via navigating.to.
	const { me } = await gql<{ me: User | null }>('{ me { id handle } }', undefined, fetch, { quiet: true });
	const isAuthPage = url.pathname === '/login' || url.pathname === '/signup';
	if (!me && !isAuthPage && url.pathname !== '/') redirect(307, '/');
	if (me && isAuthPage) redirect(307, '/');
	return { user: me };
};
