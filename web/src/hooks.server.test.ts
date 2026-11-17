import { expect, it, vi } from 'vitest';
import { handle } from './hooks.server';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const run = (url: string) => (handle as any)({ event: { url: new URL(url) }, resolve: vi.fn(() => new Response('page')) });

it('forwards the old domain and www to the same page on the main domain, for good', async () => {
	for (const host of ['sportspicks.cc', 'www.pickem.cc']) {
		const res: Response = await run(`https://${host}/add/josh?x=1`);
		expect(res.status).toBe(301);
		expect(res.headers.get('location')).toBe('https://pickem.cc/add/josh?x=1');
	}
});

it('serves the main domain and local hosts as they are', async () => {
	for (const host of ['pickem.cc', 'localhost:5173']) {
		expect(await (await run(`http://${host}/friends`)).text()).toBe('page');
	}
});
