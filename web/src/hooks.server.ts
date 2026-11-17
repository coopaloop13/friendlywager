import type { Handle } from '@sveltejs/kit/hooks';
import { SITE } from '#lib/site.js';

// The old domain and www stay attached to this Worker only to forward here, so old links and invites keep working.
const FORWARDED = new Set(['sportspicks.cc', 'www.pickem.cc']);

export const handle: Handle = ({ event, resolve }) => {
	const { hostname, pathname, search } = event.url;
	if (FORWARDED.has(hostname)) return Response.redirect(SITE + pathname + search, 301);
	return resolve(event);
};
