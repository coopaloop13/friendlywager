import { expect, it } from 'vitest';
import { GAME_FIELDS, isLocked, lockedNow, saveAction, validatePick } from './picks';

const kickoff = '2026-10-25T17:00:00Z';

it('isLocked at kickoff', () => expect(isLocked(kickoff, new Date(kickoff))).toBe(true));
it('not locked one second before', () =>
	expect(isLocked(kickoff, new Date('2026-10-25T16:59:59Z'))).toBe(false));
it('rejects ties', () => expect(validatePick('21', '21')).toBe("A pick can't be a tie"));
it('requires both', () => expect(validatePick('', '3')).toBe('Enter both scores'));
it('rejects over 200', () => expect(validatePick('201', '3')).toBe('Scores must be 0–200'));
it('accepts valid', () => expect(validatePick('24', '17')).toBeNull());

it('saveAction: one empty input is not an error, but clears stale status', () => {
	expect(saveAction('24', '', { home: 24, away: 17 })).toEqual({ kind: 'none', clear: true });
	expect(saveAction('', '3', null)).toEqual({ kind: 'none', clear: true });
});
it('saveAction: invalid full pick still errors', () =>
	expect(saveAction('21', '21', null)).toEqual({ kind: 'error', message: "A pick can't be a tie" }));
it('lockedNow: server flag or clock', () => {
	const g = { kickoffAt: kickoff, locked: false };
	expect(lockedNow(g, new Date('2026-10-25T16:59:59Z'))).toBe(false);
	expect(lockedNow(g, new Date(kickoff))).toBe(true);
	expect(lockedNow({ ...g, locked: true }, new Date('2020-01-01'))).toBe(true);
});
it('saveAction: unchanged pick is skipped', () =>
	expect(saveAction('24', '17', { home: 24, away: 17 })).toEqual({ kind: 'none' }));
it('saveAction: changed pick saves', () =>
	expect(saveAction('24', '10', { home: 24, away: 17 })).toEqual({ kind: 'save', home: 24, away: 10 }));
it('saveAction: both empty deletes only if saved', () => {
	expect(saveAction('', '', { home: 1, away: 2 })).toEqual({ kind: 'delete' });
	expect(saveAction('', '', null)).toEqual({ kind: 'none' });
});

it('requests team logos with every game', () => {
	expect(GAME_FIELDS.split(' ')).toEqual(expect.arrayContaining(['homeLogo', 'awayLogo']));
});
