// The exact strings are exercised by api/tests/test_auth.py; change both together.
export const REQUEST_CODE = 'mutation($email: String!) { requestLoginCode(email: $email) }';
export const VERIFY_CODE =
	'mutation($email: String!, $code: String!, $handle: String) { verifyLoginCode(email: $email, code: $code, handle: $handle) { token user { id handle } } }';
export const CHANGE_HANDLE = 'mutation($handle: String!) { changeHandle(handle: $handle) { id handle } }';
export const DELETE_ACCOUNT = 'mutation { deleteAccount }';

/** Drop this app's cached pages (see `remember` in gql.ts) when the account leaves the device. */
export function forget() {
	try {
		for (let i = localStorage.length - 1; i >= 0; i--) {
			const k = localStorage.key(i);
			if (k?.startsWith('fw:')) localStorage.removeItem(k);
		}
	} catch {
		// storage unusable: nothing was cached either
	}
}

const HANDLE = /^[a-z0-9_]{3,20}$/;

/** Who invited a logged-out visitor (from /add/<handle>), kept for this tab until they have signed in. */
export function rememberInvite(raw: string) {
	const handle = raw.toLowerCase();
	try {
		if (HANDLE.test(handle)) sessionStorage.setItem('invite', handle);
	} catch {
		// no storage: they land on the home page after sign-in and add the friend by handle
	}
}

export function takeInvite(): string | null {
	try {
		const handle = sessionStorage.getItem('invite');
		sessionStorage.removeItem('invite');
		return handle;
	} catch {
		return null;
	}
}
