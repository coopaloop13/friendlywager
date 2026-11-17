// The app's two looks. The choice lives on this device only; app.html applies it before first paint,
// and the colors for each live in routes/+layout.svelte.
export const LOOKS = { backyard: 'Backyard', s112: 'Section 112 (dark)' } as const;
export type Look = keyof typeof LOOKS;

const KEY = 'fw_look'; // not an `fw:` key, so logging out keeps it (see forget in account.ts)
const BAR: Record<Look, string> = { backyard: '#ffffff', s112: '#0c0d0c' }; // the browser's own bar, matched to the header

export function getLook(): Look {
	try {
		const v = localStorage.getItem(KEY);
		if (v && Object.hasOwn(LOOKS, v)) return v as Look;
	} catch {
		// storage unusable: the default look
	}
	return 'backyard';
}

export function applyLook(look: Look) {
	document.documentElement.dataset.look = look;
	document.querySelector('meta[name="theme-color"]')?.setAttribute('content', BAR[look]);
}

export function setLook(look: Look) {
	try {
		localStorage.setItem(KEY, look);
	} catch {
		// storage unusable: the look still changes until the app is closed
	}
	applyLook(look);
}
