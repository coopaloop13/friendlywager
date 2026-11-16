// The store apps are this same web app bundled in a Capacitor shell. Two things differ there: pages load from
// the device, so requests go straight to the API, and there is no cookie, so the session token is kept in the
// device's preferences and sent as a bearer token.
import { Capacitor } from '@capacitor/core';
import { Preferences } from '@capacitor/preferences';
import { API } from './site';

const KEY = 'token';

export const isNative = () => Capacitor.isNativePlatform();

export async function endpoint(): Promise<{ url: string; headers: Record<string, string> }> {
	if (!isNative()) return { url: '/graphql', headers: {} };
	const { value } = await Preferences.get({ key: KEY });
	return { url: `${API}/graphql`, headers: value ? { authorization: `Bearer ${value}` } : {} };
}

export async function signedIn(token: string) {
	if (isNative()) await Preferences.set({ key: KEY, value: token });
}

export async function signedOut() {
	if (isNative()) await Preferences.remove({ key: KEY });
}
