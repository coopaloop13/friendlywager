import { API_URL } from '$app/env/private';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ request, fetch }) => {
	const headers = new Headers();
	for (const h of ['content-type', 'cookie']) {
		const v = request.headers.get(h);
		if (v) headers.set(h, v);
	}
	const up = await fetch(`${API_URL}/graphql`, {
		method: 'POST',
		headers,
		body: await request.text()
	});
	const out = new Headers();
	const ct = up.headers.get('content-type');
	if (ct) out.set('content-type', ct);
	for (const c of up.headers.getSetCookie()) out.append('set-cookie', c);
	return new Response(await up.text(), { status: up.status, headers: out });
};
