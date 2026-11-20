import { writable } from 'svelte/store';
import { endpoint } from './native';

export class GqlError extends Error {
	constructor(
		message: string,
		public code?: string
	) {
		super(message);
	}
}

/** In-flight non-quiet requests; drives the global loading overlay. */
export const pending = writable(0);

export async function gql<T>(
	query: string,
	variables?: Record<string, unknown>,
	f: typeof fetch = fetch,
	{ quiet = false, retries = [500, 1500, 4000] }: { quiet?: boolean; retries?: number[] } = {}
): Promise<T> {
	if (!quiet) pending.update((n) => n + 1);
	try {
		const { url, headers } = await endpoint();
		const send = () =>
			f(url, {
				method: 'POST',
				headers: { 'content-type': 'application/json', ...headers },
				body: JSON.stringify({ query, variables })
			});
		let res = await send();
		// 5xx means the proxy or a starting container, never a resolver (those answer 200 with `errors`).
		// ponytail: mutations are retried too; every one is an upsert or safe to repeat except verifyLoginCode,
		// which would report an invalid code on a retry that follows a lost success. Skip mutations if that bites.
		for (const ms of retries) {
			if (res.status < 500) break;
			await new Promise((r) => setTimeout(r, ms));
			res = await send();
		}
		let json;
		try {
			json = await res.json();
		} catch {
			throw new GqlError(`Request failed (${res.status})`);
		}
		if (json.errors?.length) {
			const e = json.errors[0];
			throw new GqlError(e.message, e.extensions?.code);
		}
		return json.data as T;
	} finally {
		if (!quiet) pending.update((n) => n - 1);
	}
}

/** Last good response for a key: pages render it at once and refresh quietly. Storage is optional. */
export function cached<T>(key: string): T | null {
	try {
		const v = localStorage.getItem(`fw:${key}`);
		return v ? (JSON.parse(v) as T) : null;
	} catch {
		return null;
	}
}

export function remember(key: string, value: unknown) {
	try {
		localStorage.setItem(`fw:${key}`, JSON.stringify(value));
	} catch {
		// private mode or full: the next load is just slower
	}
}

/**
 * For data that rarely changes: `show` gets the last copy at once (if there is one), then the new answer,
 * which is kept for next time. `load` is told to be quiet when a copy is already on screen.
 * A failed refresh rejects and leaves the copy where it is.
 */
export async function fresh<T>(key: string, load: (quiet: boolean) => Promise<T>, show: (value: T) => void) {
	const hit = cached<T>(key);
	if (hit !== null) show(hit);
	const value = await load(hit !== null);
	show(value);
	remember(key, value);
}
