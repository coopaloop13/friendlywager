export type WeekLine = { seasonType: number; week: number; pointsFor: number; pointsAgainst: number };
export type Row = {
	userId: string;
	handle: string;
	pointsFor: number;
	pointsAgainst: number;
	weeksWon: number;
	weeksLost: number;
	weeksTied: number;
	weeks: WeekLine[];
};
export type Stats = { picked: number; winners: number; exact: number };
export type Outcome = 'W' | 'L' | 'T';
export type SortBy = 'weeks' | 'points';

export const CURRENT_WEEK_QUERY = 'query($l: League!) { currentWeek(league: $l) { season seasonType week } }';
export const BOARD_QUERY =
	'query($l: League!, $s: Int!) { leaderboard(league: $l, season: $s) { userId handle pointsFor pointsAgainst weeksWon weeksLost weeksTied weeks { seasonType week pointsFor pointsAgainst } } seasonStats(league: $l, season: $s) { picked winners exact } }';

export const outcome = (w: WeekLine): Outcome =>
	w.pointsFor > w.pointsAgainst ? 'W' : w.pointsFor < w.pointsAgainst ? 'L' : 'T';

export function streak(weeks: WeekLine[]): string {
	if (!weeks.length) return '';
	const last = outcome(weeks[weeks.length - 1]);
	let n = 0;
	for (let i = weeks.length - 1; i >= 0 && outcome(weeks[i]) === last; i--) n++;
	return `${last}${n}`;
}

export const thisWeek = (weeks: WeekLine[], cur: { seasonType: number; week: number }): WeekLine | undefined =>
	weeks.find((w) => w.seasonType === cur.seasonType && w.week === cur.week);

export const settled = (weeks: WeekLine[], cur: { seasonType: number; week: number } | null): WeekLine[] =>
	cur ? weeks.filter((w) => !(w.seasonType === cur.seasonType && w.week === cur.week)) : weeks;

export const weekLabel = (w: { seasonType: number; week: number }): string =>
	`${w.seasonType === 3 ? 'P' : w.seasonType === 1 ? 'Pre' : 'W'}${w.week}`;

export const diff = (r: Row): number => r.pointsFor - r.pointsAgainst;

export function lead(r: Row): 'lead' | 'trail' | 'even' {
	const d = r.weeksWon - r.weeksLost || diff(r);
	return d > 0 ? 'lead' : d < 0 ? 'trail' : 'even';
}

export const summary = (rows: Row[]) => ({
	won: rows.reduce((n, r) => n + r.weeksWon, 0),
	lost: rows.reduce((n, r) => n + r.weeksLost, 0),
	tied: rows.reduce((n, r) => n + r.weeksTied, 0),
	pointsFor: rows.reduce((n, r) => n + r.pointsFor, 0),
	pointsAgainst: rows.reduce((n, r) => n + r.pointsAgainst, 0)
});

export const sortRows = (rows: Row[], by: SortBy): Row[] =>
	by === 'weeks' ? rows : [...rows].sort((a, b) => diff(b) - diff(a) || a.handle.localeCompare(b.handle));

export const pct = (part: number, whole: number): string =>
	whole === 0 ? '' : `${Math.round((100 * part) / whole)}%`;
