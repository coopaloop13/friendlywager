import { expect, it } from 'vitest';
import { load } from './+layout';

const as = (me: unknown) => () => Promise.resolve(Response.json({ data: { me } }));
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const run = (path: string, me: unknown) => (load as any)({ fetch: as(me), url: new URL(path, 'http://x') });
const target = (p: Promise<unknown>) => p.then(() => null, (r) => r.location);

it('sends logged-out visitors to the landing page at root', async () => {
	expect(await target(run('/friends', null))).toBe('/');
});

it('lets logged-out visitors see root, login and signup', async () => {
	for (const p of ['/', '/login', '/signup']) expect(await target(run(p, null))).toBeNull();
});

it('sends logged-in users from login to home', async () => {
	expect(await target(run('/login', { id: '1', handle: 'a' }))).toBe('/');
});

it('does not drive the loading overlay (tap preload would block the click)', async () => {
	const { get } = await import('svelte/store');
	const { pending } = await import('#lib/gql.js');
	let done!: (r: Response) => void;
	const slow = () => new Promise<Response>((r) => (done = r));
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const p = (load as any)({ fetch: slow, url: new URL('/', 'http://x') });
	expect(get(pending)).toBe(0);
	done(Response.json({ data: { me: null } }));
	await p;
});
