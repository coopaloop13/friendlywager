import { expect, it, vi } from 'vitest';
import { gql, GqlError } from './gql';

it('throws GqlError with status message on non-JSON body', async () => {
	const f = vi.fn().mockResolvedValue(new Response('<html>bad gateway</html>', { status: 502 }));
	const err = await gql('{me{id}}', undefined, f, { retries: [] }).catch((e) => e);
	expect(err).toBeInstanceOf(GqlError);
	expect((err as GqlError).message).toBe('Request failed (502)');
});

it('counts in-flight requests in `pending`, except quiet ones', async () => {
	const { get } = await import('svelte/store');
	const { pending } = await import('./gql');
	let done!: (r: Response) => void;
	const f = vi.fn(() => new Promise<Response>((r) => (done = r)));
	const p = gql('{me{id}}', undefined, f);
	expect(get(pending)).toBe(1);
	done(Response.json({ data: {} }));
	await p;
	expect(get(pending)).toBe(0);
	const q = gql('{me{id}}', undefined, f, { quiet: true });
	expect(get(pending)).toBe(0);
	done(Response.json({ data: {} }));
	await q;
});

it('remembers the last response per key and tolerates unusable storage', async () => {
	const { cached, remember } = await import('./gql');
	const store = new Map<string, string>();
	vi.stubGlobal('localStorage', {
		getItem: (k: string) => store.get(k) ?? null,
		setItem: (k: string, v: string) => void store.set(k, v)
	});
	expect(cached('board:1:nfl')).toBeNull();
	remember('board:1:nfl', { rows: [1] });
	expect(cached('board:1:nfl')).toEqual({ rows: [1] });
	const deny = () => { throw new Error('denied'); };
	vi.stubGlobal('localStorage', { getItem: deny, setItem: deny });
	expect(() => remember('x', 1)).not.toThrow();
	expect(cached('board:1:nfl')).toBeNull();
	vi.unstubAllGlobals();
});

it('retries 5xx responses (container cold start) and returns the first good one', async () => {
	const f = vi
		.fn()
		.mockResolvedValueOnce(new Response('starting', { status: 500 }))
		.mockResolvedValueOnce(new Response('API unavailable', { status: 502 }))
		.mockResolvedValueOnce(Response.json({ data: { me: null } }));
	expect(await gql('{me{id}}', undefined, f, { retries: [0, 0] })).toEqual({ me: null });
	expect(f).toHaveBeenCalledTimes(3);
});

it('gives up after the last retry and does not retry client errors', async () => {
	const down = vi.fn(() => Promise.resolve(new Response('starting', { status: 500 })));
	await expect(gql('{me{id}}', undefined, down, { retries: [0, 0] })).rejects.toThrow('Request failed (500)');
	expect(down).toHaveBeenCalledTimes(3);
	const bad = vi.fn(() => Promise.resolve(new Response('nope', { status: 400 })));
	await expect(gql('{me{id}}', undefined, bad, { retries: [0, 0] })).rejects.toThrow('Request failed (400)');
	expect(bad).toHaveBeenCalledTimes(1);
});
