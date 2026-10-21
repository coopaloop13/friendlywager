import { redirect } from '@sveltejs/kit';
import { gql } from '#lib/gql.js';
import type { LayoutLoad } from './$types';

export const ssr = false;

export type User = { id: string; handle: string };

export const load: LayoutLoad = async ({ fetch, url }) => {
	const { me } = await gql<{ me: User | null }>('{ me { id handle } }', undefined, fetch);
	const isAuthPage = ['/welcome', '/login', '/signup'].includes(url.pathname);
	if (!me && !isAuthPage) redirect(307, '/welcome');
	if (me && isAuthPage) redirect(307, '/');
	return { user: me };
};
