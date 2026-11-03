import { expect, it } from 'vitest';
import { diff, lead, outcome, pct, settled, sortRows, streak, summary, thisWeek, weekLabel, type Row, type WeekLine } from './standings';

const w = (seasonType: number, week: number, pointsFor: number, pointsAgainst: number): WeekLine =>
	({ seasonType, week, pointsFor, pointsAgainst });
const row = (p: Partial<Row>): Row =>
	({ userId: 'u', handle: 'h', pointsFor: 0, pointsAgainst: 0, weeksWon: 0, weeksLost: 0, weeksTied: 0, weeks: [], ...p });

it('derives the week outcome from points', () => {
	expect([outcome(w(2, 1, 3, 1)), outcome(w(2, 1, 1, 3)), outcome(w(2, 1, 0, 0))]).toEqual(['W', 'L', 'T']);
});

it('streak is the trailing run of equal outcomes, blank when empty', () => {
	expect(streak([])).toBe('');
	expect(streak([w(2, 1, 0, 2), w(2, 2, 3, 1), w(2, 3, 2, 1), w(3, 1, 4, 0)])).toBe('W3');
	expect(streak([w(2, 1, 3, 1), w(2, 2, 1, 1)])).toBe('T1');
});

it('thisWeek finds the current week or nothing before kickoff', () => {
	const weeks = [w(2, 8, 5, 2), w(2, 9, 1, 0)];
	expect(thisWeek(weeks, { seasonType: 2, week: 9 })).toEqual(w(2, 9, 1, 0));
	expect(thisWeek(weeks, { seasonType: 2, week: 10 })).toBeUndefined();
	expect(thisWeek(weeks, { seasonType: 3, week: 9 })).toBeUndefined();
});

it('labels weeks by season type', () => {
	expect([weekLabel(w(2, 5, 0, 0)), weekLabel(w(3, 1, 0, 0)), weekLabel(w(1, 1, 0, 0))]).toEqual(['W5', 'P1', 'Pre1']);
});

it('lead compares weeks, then point differential', () => {
	expect(lead(row({ weeksWon: 2, weeksLost: 1 }))).toBe('lead');
	expect(lead(row({ weeksWon: 1, weeksLost: 2, pointsFor: 9 }))).toBe('trail');
	expect(lead(row({ weeksWon: 1, weeksLost: 1, pointsFor: 4, pointsAgainst: 2 }))).toBe('lead');
	expect(lead(row({ weeksWon: 1, weeksLost: 1, pointsFor: 2, pointsAgainst: 4 }))).toBe('trail');
	expect(lead(row({}))).toBe('even');
});

it('summary sums every friend', () => {
	const rows = [row({ weeksWon: 2, weeksTied: 1, pointsFor: 10, pointsAgainst: 4 }), row({ weeksLost: 1, pointsFor: 1, pointsAgainst: 3 })];
	expect(summary(rows)).toEqual({ won: 2, lost: 1, tied: 1, pointsFor: 11, pointsAgainst: 7 });
});

it('sortRows keeps server order for weeks and sorts by differential for points', () => {
	const a = row({ handle: 'a', weeksWon: 3, pointsFor: 5, pointsAgainst: 5 });
	const b = row({ handle: 'b', weeksWon: 1, pointsFor: 9, pointsAgainst: 2 });
	const c = row({ handle: 'c', weeksWon: 1, pointsFor: 9, pointsAgainst: 2 });
	expect(sortRows([a, b, c], 'weeks').map((r) => r.handle)).toEqual(['a', 'b', 'c']);
	expect(sortRows([c, a, b], 'points').map((r) => r.handle)).toEqual(['b', 'c', 'a']);
	expect(diff(b)).toBe(7);
});

it('pct rounds and is blank with nothing decided', () => {
	expect(pct(0, 0)).toBe('');
	expect(pct(2, 3)).toBe('67%');
});

it('settled drops the current week and keeps the rest in order', () => {
	const weeks = [w(2, 7, 1, 0), w(2, 8, 0, 1), w(2, 9, 0, 0)];
	expect(settled(weeks, { seasonType: 2, week: 8 })).toEqual([w(2, 7, 1, 0), w(2, 9, 0, 0)]);
});

it('settled returns everything with no cur or no match', () => {
	const weeks = [w(2, 7, 1, 0), w(2, 8, 0, 1)];
	expect(settled(weeks, null)).toEqual(weeks);
	expect(settled(weeks, { seasonType: 3, week: 8 })).toEqual(weeks);
});

it('settled does not mutate its input', () => {
	const weeks = [w(2, 7, 1, 0), w(2, 8, 0, 1)];
	settled(weeks, { seasonType: 2, week: 8 });
	expect(weeks).toEqual([w(2, 7, 1, 0), w(2, 8, 0, 1)]);
});

it('streak over settled weeks ignores the in-progress week', () => {
	const weeks = [w(2, 6, 2, 1), w(2, 7, 3, 0), w(2, 8, 1, 0), w(2, 9, 0, 0)];
	expect(streak(settled(weeks, { seasonType: 2, week: 9 }))).toBe('W3');
});
