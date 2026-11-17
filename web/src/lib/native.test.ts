import { beforeEach, expect, it, vi } from 'vitest';

const state = { native: false, prefs: new Map<string, string>() };
vi.mock('@capacitor/core', () => ({ Capacitor: { isNativePlatform: () => state.native } }));
vi.mock('@capacitor/preferences', () => ({
	Preferences: {
		get: async ({ key }: { key: string }) => ({ value: state.prefs.get(key) ?? null }),
		set: async ({ key, value }: { key: string; value: string }) => void state.prefs.set(key, value),
		remove: async ({ key }: { key: string }) => void state.prefs.delete(key)
	}
}));

import { endpoint, signedIn, signedOut } from './native';
import { gql } from './gql';

beforeEach(() => {
	state.native = false;
	state.prefs.clear();
});

it('on the web, talks to the same-origin proxy and leaves auth to the cookie', async () => {
	await signedIn('tok'); // nothing to keep: the cookie is the session
	expect(await endpoint()).toEqual({ url: '/graphql', headers: {} });
	expect(state.prefs.size).toBe(0);
});

it('in the app, talks to the API directly with the stored token', async () => {
	state.native = true;
	expect(await endpoint()).toEqual({ url: 'https://api.pickem.cc/graphql', headers: {} });
	await signedIn('tok');
	expect(await endpoint()).toEqual({
		url: 'https://api.pickem.cc/graphql',
		headers: { authorization: 'Bearer tok' }
	});
	await signedOut();
	expect((await endpoint()).headers).toEqual({});
});

it('gql() sends requests where endpoint() says', async () => {
	state.native = true;
	await signedIn('tok');
	const f = vi.fn().mockResolvedValue(Response.json({ data: { ok: 1 } }));
	await gql('{ok}', undefined, f);
	const [url, init] = f.mock.calls[0];
	expect(url).toBe('https://api.pickem.cc/graphql');
	expect(init.headers).toEqual({ 'content-type': 'application/json', authorization: 'Bearer tok' });
});
