import { expect, it, vi } from 'vitest';
import { load } from './+layout';

vi.mock('$app/navigation', () => ({ invalidateAll: vi.fn(() => Promise.resolve()) }));

const as = (me: unknown) => () => Promise.resolve(Response.json({ data: { me } }));
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const run = (path: string, me: unknown) => (load as any)({ fetch: as(me), url: new URL(path, 'http://x'), untrack: (f: () => unknown) => f() });
const target = (p: Promise<unknown>) => p.then(() => null, (r) => r.location);

it('sends logged-out visitors to the landing page at root', async () => {
	expect(await target(run('/friends', null))).toBe('/');
});

it('lets logged-out visitors see root and login', async () => {
	for (const p of ['/', '/login']) expect(await target(run(p, null))).toBeNull();
});

it('sends the retired signup page to login, where new accounts are made now', async () => {
	expect(await target(run('/signup', null))).toBe('/login');
});

it('sends logged-in users from login to home', async () => {
	expect(await target(run('/login', { id: '1', handle: 'a' }))).toBe('/');
});

it('does not drive the loading overlay (tap preload would block the click)', async () => {
	const { get } = await import('svelte/store');
	const { pending } = await import('#lib/gql.js');
	let done!: (r: Response) => void;
	const slow = vi.fn(() => new Promise<Response>((r) => (done = r)));
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const p = (load as any)({ fetch: slow, url: new URL('/', 'http://x'), untrack: (f: () => unknown) => f() });
	expect(get(pending)).toBe(0);
	await vi.waitFor(() => expect(slow).toHaveBeenCalled()); // the request goes out a tick later
	done(Response.json({ data: { me: null } }));
	await p;
});

it('reads the url without tracking it, so tab switches do not refetch me', async () => {
	const untrack = vi.fn((f: () => unknown) => f());
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const p = (load as any)({ fetch: as({ id: '1', handle: 'a' }), url: new URL('/login', 'http://x'), untrack });
	expect(await target(p)).toBe('/');
	expect(untrack).toHaveBeenCalled();
});

it('reports an unreachable API instead of throwing or redirecting', async () => {
	vi.useFakeTimers();
	const down = () => Promise.resolve(new Response('API unavailable', { status: 502 }));
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const p = (load as any)({ fetch: down, url: new URL('/friends', 'http://x'), untrack: (f: () => unknown) => f() });
	await vi.runAllTimersAsync();
	expect(await p).toEqual({ user: null, unavailable: true });
	vi.useRealTimers();
});

it('lets logged-out visitors read the terms and privacy pages', async () => {
	for (const p of ['/terms', '/privacy']) expect(await target(run(p, null))).toBeNull();
});

it('sends a logged-out invite link to sign-in and remembers who invited', async () => {
	const store = new Map<string, string>();
	vi.stubGlobal('sessionStorage', {
		setItem: (k: string, v: string) => void store.set(k, v),
		getItem: (k: string) => store.get(k) ?? null,
		removeItem: (k: string) => void store.delete(k)
	});
	expect(await target(run('/add/Maria', null))).toBe('/login');
	const { takeInvite } = await import('#lib/account.js');
	expect(takeInvite()).toBe('maria');
	expect(takeInvite()).toBeNull(); // used once
	expect(await target(run('/add/not a handle!', null))).toBe('/login');
	expect(takeInvite()).toBeNull();
	vi.unstubAllGlobals();
});

it('lets a logged-in user open an invite link', async () => {
	expect(await target(run('/add/maria', { id: '1', handle: 'a' }))).toBeNull();
});

// a signed-in user kept on the device: the app opens on it and checks the session behind the page
function storage(entries: Record<string, unknown> = {}) {
	const store = new Map(Object.entries(entries).map(([k, v]) => [k, JSON.stringify(v)]));
	vi.stubGlobal('localStorage', {
		getItem: (k: string) => store.get(k) ?? null,
		setItem: (k: string, v: string) => void store.set(k, v),
		removeItem: (k: string) => void store.delete(k),
		key: (i: number) => [...store.keys()][i] ?? null,
		get length() {
			return store.size;
		}
	});
	return store;
}
const josh = { id: '1', handle: 'josh' };

it('opens on the kept user without waiting for the server', async () => {
	storage({ 'fw:me': josh });
	const never = vi.fn(() => new Promise<Response>(() => {}));
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const out = await (load as any)({ fetch: never, url: new URL('/friends', 'http://x'), untrack: (f: () => unknown) => f() });
	expect(out).toEqual({ user: josh, unavailable: false });
	vi.unstubAllGlobals();
});

it('keeps the user after a sign-in answer, and not a signed-out one', async () => {
	const store = storage();
	await run('/', null);
	expect(store.has('fw:me')).toBe(false);
	await run('/', josh);
	expect(JSON.parse(store.get('fw:me')!)).toEqual(josh);
	vi.unstubAllGlobals();
});

it('drops everything kept and reloads when the server says the session is gone', async () => {
	const { invalidateAll } = await import('$app/navigation');
	vi.mocked(invalidateAll).mockClear();
	const store = storage({ 'fw:me': josh, 'fw:friends:1': { friends: [] }, fw_look: 'backyard' });
	expect(await run('/friends', null)).toEqual({ user: josh, unavailable: false });
	await vi.waitFor(() => expect(invalidateAll).toHaveBeenCalledTimes(1));
	expect([...store.keys()]).toEqual(['fw_look']);
	vi.unstubAllGlobals();
});

it('takes a new handle from the server and reloads', async () => {
	const { invalidateAll } = await import('$app/navigation');
	vi.mocked(invalidateAll).mockClear();
	const store = storage({ 'fw:me': josh });
	await run('/', { id: '1', handle: 'joshua' });
	await vi.waitFor(() => expect(invalidateAll).toHaveBeenCalledTimes(1));
	expect(JSON.parse(store.get('fw:me')!)).toEqual({ id: '1', handle: 'joshua' });
	vi.unstubAllGlobals();
});

it('stays on the kept user when the check agrees or the API is down', async () => {
	const { invalidateAll } = await import('$app/navigation');
	vi.mocked(invalidateAll).mockClear();
	const store = storage({ 'fw:me': josh });
	await run('/', josh);
	const down = vi.fn(() => Promise.resolve(new Response('API unavailable', { status: 400 })));
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	const out = await (load as any)({ fetch: down, url: new URL('/', 'http://x'), untrack: (f: () => unknown) => f() });
	expect(out).toEqual({ user: josh, unavailable: false });
	await vi.waitFor(() => expect(down).toHaveBeenCalled());
	await new Promise((r) => setTimeout(r, 10));
	expect(invalidateAll).not.toHaveBeenCalled();
	expect(JSON.parse(store.get('fw:me')!)).toEqual(josh);
	vi.unstubAllGlobals();
});
