import { beforeEach, expect, it, vi } from 'vitest';

const state = { native: true, permission: 'granted', calls: [] as string[] };
vi.mock('@capacitor/core', () => ({
	Capacitor: { isNativePlatform: () => state.native, getPlatform: () => 'ios' }
}));
vi.mock('@capacitor/preferences', () => ({
	Preferences: { get: async () => ({ value: 'tok' }), set: async () => {}, remove: async () => {} }
}));
vi.mock('@capacitor-firebase/messaging', () => ({
	FirebaseMessaging: {
		requestPermissions: async () => (state.calls.push('ask'), { receive: state.permission }),
		getToken: async () => ({ token: 'device-1' }),
		deleteToken: async () => void state.calls.push('deleteToken')
	}
}));

import { disablePush, enablePush, REGISTER, UNREGISTER } from './push';

const sent = () => {
	const f = vi.fn(async () => Response.json({ data: {} }));
	vi.stubGlobal('fetch', f);
	return () => f.mock.calls.map((c) => JSON.parse((c as unknown as [string, { body: string }])[1].body));
};

beforeEach(() => {
	state.native = true;
	state.permission = 'granted';
	state.calls = [];
});

it('does nothing on the web', async () => {
	state.native = false;
	const bodies = sent();
	await enablePush();
	await disablePush();
	expect(bodies()).toEqual([]);
	expect(state.calls).toEqual([]);
});

it('registers this device once the user allows notifications', async () => {
	const bodies = sent();
	await enablePush();
	expect(bodies()).toEqual([{ query: REGISTER, variables: { token: 'device-1', platform: 'ios' } }]);
});

it('registers nothing when the user says no', async () => {
	state.permission = 'denied';
	const bodies = sent();
	await enablePush();
	expect(bodies()).toEqual([]);
});

it('unregisters the device on the way out, and never blocks leaving', async () => {
	const bodies = sent();
	await disablePush();
	expect(bodies()).toEqual([{ query: UNREGISTER, variables: { token: 'device-1' } }]);
	expect(state.calls).toContain('deleteToken');
	vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
	await expect(disablePush()).resolves.toBeUndefined();
});
