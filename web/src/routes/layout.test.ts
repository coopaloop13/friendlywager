import { expect, it } from 'vitest';
import { load } from './+layout';

const as = (me: unknown) => () => Promise.resolve(Response.json({ data: { me } }));
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const run = (path: string, me: unknown) => (load as any)({ fetch: as(me), url: new URL(path, 'http://x') });
const target = (p: Promise<unknown>) => p.then(() => null, (r) => r.location);

it('sends logged-out visitors to the landing page', async () => {
	expect(await target(run('/', null))).toBe('/welcome');
	expect(await target(run('/friends', null))).toBe('/welcome');
});

it('lets logged-out visitors see welcome, login and signup', async () => {
	for (const p of ['/welcome', '/login', '/signup']) expect(await target(run(p, null))).toBeNull();
});

it('sends logged-in users from welcome to home', async () => {
	expect(await target(run('/welcome', { id: '1', handle: 'a' }))).toBe('/');
});
