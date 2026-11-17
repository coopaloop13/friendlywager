import { afterEach, expect, it, vi } from 'vitest';
import { applyLook, getLook, setLook } from './look';

function stub(initial?: string) {
	const store = new Map<string, string>(initial ? [['fw_look', initial]] : []);
	const meta = { content: '', setAttribute: (_: string, v: string) => void (meta.content = v) };
	const root = { dataset: {} as Record<string, string> };
	vi.stubGlobal('localStorage', {
		getItem: (k: string) => store.get(k) ?? null,
		setItem: (k: string, v: string) => void store.set(k, v)
	});
	vi.stubGlobal('document', { documentElement: root, querySelector: () => meta });
	return { store, meta, root };
}

afterEach(() => vi.unstubAllGlobals());

it('starts on Backyard', () => {
	stub();
	expect(getLook()).toBe('backyard');
});

it('ignores a stored value that is not a look', () => {
	stub('toString');
	expect(getLook()).toBe('backyard');
});

it('falls back to Backyard when storage is unusable', () => {
	vi.stubGlobal('localStorage', {
		getItem: () => {
			throw new Error('blocked');
		}
	});
	expect(getLook()).toBe('backyard');
});

it('remembers the chosen look on this device and applies it', () => {
	const { store, meta, root } = stub();
	setLook('s112');
	expect(store.get('fw_look')).toBe('s112');
	expect(getLook()).toBe('s112');
	expect(root.dataset.look).toBe('s112');
	expect(meta.content).toBe('#0c0d0c');
});

it('survives logging out (forget only drops fw: keys)', async () => {
	const { store } = stub('s112');
	vi.stubGlobal('localStorage', {
		length: 1,
		key: () => 'fw_look',
		removeItem: (k: string) => void store.delete(k),
		getItem: (k: string) => store.get(k) ?? null
	});
	(await import('./account')).forget();
	expect(getLook()).toBe('s112');
});

it('applies a look without storing it', () => {
	const { store, root } = stub();
	applyLook('backyard');
	expect(root.dataset.look).toBe('backyard');
	expect(store.size).toBe(0);
});
