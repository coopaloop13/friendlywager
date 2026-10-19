export class GqlError extends Error {
	constructor(
		message: string,
		public code?: string
	) {
		super(message);
	}
}

export async function gql<T>(
	query: string,
	variables?: Record<string, unknown>,
	f: typeof fetch = fetch
): Promise<T> {
	const res = await f('/graphql', {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: JSON.stringify({ query, variables })
	});
	const json = await res.json();
	if (json.errors?.length) {
		const e = json.errors[0];
		throw new GqlError(e.message, e.extensions?.code);
	}
	return json.data as T;
}
