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
	{ quiet = false } = {}
): Promise<T> {
	if (!quiet) pending.update((n) => n + 1);
	try {
		const res = await f('/graphql', {
			method: 'POST',
			headers: { 'content-type': 'application/json' },
			body: JSON.stringify({ query, variables })
		});
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
