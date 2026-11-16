import { expect, it, vi } from 'vitest';
import { forget } from './account';

it('forget() drops every cached fw: entry and nothing else', () => {
	const store = new Map([
		['fw:week:1:NFL', '{}'],
		['fw:board:1:CFB', '{}'],
		['other-app', 'keep']
	]);
	vi.stubGlobal('localStorage', {
		get length() {
			return store.size;
		},
		key: (i: number) => [...store.keys()][i] ?? null,
		removeItem: (k: string) => void store.delete(k)
	});
	forget();
	expect([...store.keys()]).toEqual(['other-app']);
	vi.unstubAllGlobals();
});

it('forget() tolerates unusable storage', () => {
	vi.stubGlobal('localStorage', {
		get length(): number {
			throw new Error('denied');
		}
	});
	expect(() => forget()).not.toThrow();
	vi.unstubAllGlobals();
});

it('invites survive unusable storage as "no invite"', async () => {
	const { rememberInvite, takeInvite } = await import('./account');
	vi.stubGlobal('sessionStorage', {
		setItem() {
			throw new Error('denied');
		},
		getItem() {
			throw new Error('denied');
		}
	});
	expect(() => rememberInvite('maria')).not.toThrow();
	expect(takeInvite()).toBeNull();
	vi.unstubAllGlobals();
});
