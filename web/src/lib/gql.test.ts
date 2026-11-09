import { expect, it, vi } from 'vitest';
import { gql, GqlError } from './gql';

it('throws GqlError with status message on non-JSON body', async () => {
	const f = vi.fn().mockResolvedValue(new Response('<html>bad gateway</html>', { status: 502 }));
	const err = await gql('{me{id}}', undefined, f).catch((e) => e);
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
