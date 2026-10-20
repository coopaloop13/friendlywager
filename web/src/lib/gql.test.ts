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
