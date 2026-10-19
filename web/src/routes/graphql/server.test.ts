import { describe, expect, it, vi } from 'vitest';

vi.mock('$app/env/private', () => ({ API_URL: 'http://api:8000' }));

import { POST } from './+server';

function call(upstream: Response, headers: Record<string, string> = {}) {
	const f = vi.fn().mockResolvedValue(upstream);
	const request = new Request('http://localhost/graphql', {
		method: 'POST',
		headers: { 'content-type': 'application/json', ...headers },
		body: '{"query":"{me{id}}"}'
	});
	return { f, res: POST({ request, fetch: f } as never) };
}

describe('graphql proxy', () => {
	it('forwards cookie to API', async () => {
		const { f, res } = call(new Response('{}'), { cookie: 'fw_session=abc' });
		await res;
		const [url, init] = f.mock.calls[0];
		expect(url).toBe('http://api:8000/graphql');
		expect(init.method).toBe('POST');
		expect(init.headers.get('cookie')).toBe('fw_session=abc');
		expect(init.headers.get('content-type')).toBe('application/json');
		expect(await new Response(init.body).text()).toBe('{"query":"{me{id}}"}');
	});

	it('passes set-cookie back', async () => {
		const up = new Response('{"data":{}}', { headers: { 'content-type': 'application/json' } });
		up.headers.append('set-cookie', 'fw_session=abc; HttpOnly');
		up.headers.append('set-cookie', 'other=1; Path=/');
		const res = await call(up).res;
		expect(res.headers.getSetCookie()).toEqual(['fw_session=abc; HttpOnly', 'other=1; Path=/']);
		expect(await res.text()).toBe('{"data":{}}');
	});

	it('passes status through', async () => {
		const res = await call(new Response('{"errors":[]}', { status: 502 })).res;
		expect(res.status).toBe(502);
	});

	it('returns 502 graphql error when API is unreachable', async () => {
		const f = vi.fn().mockRejectedValue(new TypeError('fetch failed'));
		const request = new Request('http://localhost/graphql', { method: 'POST', body: '{}' });
		const res = await POST({ request, fetch: f } as never);
		expect(res.status).toBe(502);
		expect(await res.json()).toEqual({
			errors: [{ message: 'API unavailable', extensions: { code: 'UPSTREAM_UNAVAILABLE' } }]
		});
	});
});
