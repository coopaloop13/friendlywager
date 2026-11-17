// "Picks lock soon" reminders, store apps only. The server sends them (api/app/reminders.py); this file only
// tells it which device belongs to the signed-in user.
import { Capacitor } from '@capacitor/core';
import { FirebaseMessaging } from '@capacitor-firebase/messaging';
import { gql } from './gql';
import { isNative } from './native';

// The exact strings are exercised by api/tests/test_reminders.py; change both together.
export const REGISTER =
	'mutation($token: String!, $platform: String!) { registerDevice(token: $token, platform: $platform) }';
export const UNREGISTER = 'mutation($token: String!) { unregisterDevice(token: $token) }';

const quiet = { quiet: true, retries: [] };

const register = (token: string) => gql(REGISTER, { token, platform: Capacitor.getPlatform() }, fetch, quiet);
let listening = false;

/** Ask for permission (the system only prompts once) and register the device. Safe to call on every launch. */
export async function enablePush() {
	if (!isNative()) return;
	try {
		if ((await FirebaseMessaging.requestPermissions()).receive !== 'granted') return;
		// iOS, first launch: right after Allow, Apple's token is often not in yet and getToken throws.
		// The token then arrives through this event (also when it is later replaced). Registering twice is harmless.
		if (!listening) {
			listening = true;
			await FirebaseMessaging.addListener('tokenReceived', ({ token }) => {
				register(token).catch((e) => console.warn('push not enabled', e));
			});
		}
		await register((await FirebaseMessaging.getToken()).token);
	} catch (e) {
		console.warn('push not enabled', e); // reminders are a nicety; the app works without them
	}
}

/** Before logging out or deleting the account: this phone stops getting that user's reminders. */
export async function disablePush() {
	if (!isNative()) return;
	try {
		const { token } = await FirebaseMessaging.getToken();
		await gql(UNREGISTER, { token }, fetch, quiet);
		await FirebaseMessaging.deleteToken();
	} catch (e) {
		console.warn('push not disabled', e);
	}
}
