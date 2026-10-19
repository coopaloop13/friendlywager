import { expect, it, vi } from 'vitest';
import { gql, GqlError } from './gql';

it('throws GqlError with status message on non-JSON body', async () => {
	const f = vi.fn().mockResolvedValue(new Response('<html>bad gateway</html>', { status: 502 }));
	const err = await gql('{me{id}}', undefined, f).catch((e) => e);
	expect(err).toBeInstanceOf(GqlError);
	expect((err as GqlError).message).toBe('Request failed (502)');
});
