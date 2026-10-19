import { expect, it } from 'vitest';
import { isLocked, saveAction, validatePick } from './picks';

const kickoff = '2026-10-25T17:00:00Z';

it('isLocked at kickoff', () => expect(isLocked(kickoff, new Date(kickoff))).toBe(true));
it('not locked one second before', () =>
	expect(isLocked(kickoff, new Date('2026-10-25T16:59:59Z'))).toBe(false));
it('rejects ties', () => expect(validatePick('21', '21')).toBe("A pick can't be a tie"));
it('requires both', () => expect(validatePick('', '3')).toBe('Enter both scores'));
it('rejects over 200', () => expect(validatePick('201', '3')).toBe('Scores must be 0–200'));
it('accepts valid', () => expect(validatePick('24', '17')).toBeNull());

it('saveAction: one empty input is an error, not silence', () =>
	expect(saveAction('24', '', { home: 24, away: 17 })).toEqual({ kind: 'error', message: 'Enter both scores' }));
it('saveAction: unchanged pick is skipped', () =>
	expect(saveAction('24', '17', { home: 24, away: 17 })).toEqual({ kind: 'none' }));
it('saveAction: changed pick saves', () =>
	expect(saveAction('24', '10', { home: 24, away: 17 })).toEqual({ kind: 'save', home: 24, away: 10 }));
it('saveAction: both empty deletes only if saved', () => {
	expect(saveAction('', '', { home: 1, away: 2 })).toEqual({ kind: 'delete' });
	expect(saveAction('', '', null)).toEqual({ kind: 'none' });
});
