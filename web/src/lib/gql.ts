import { writable } from 'svelte/store';

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
		const send = () =>
			f('/graphql', {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ query, variables })
			});
		let res = await send();
		// 5xx means the proxy or a starting container, never a resolver (those answer 200 with `errors`).
		// ponytail: mutations are retried too; every one is an upsert or safe to repeat except signUp,
		// which would report "taken" on a retry that follows a lost success. Skip mutations if that bites.
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
