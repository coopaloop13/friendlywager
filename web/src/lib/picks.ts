export function isLocked(kickoffAt: string, now: Date): boolean {
	return now.getTime() >= new Date(kickoffAt).getTime();
}

export function validatePick(home: string, away: string): string | null {
	const h = home.trim();
	const a = away.trim();
	if (!/^\d+$/.test(h) || !/^\d+$/.test(a)) return 'Enter both scores';
	if (+h > 200 || +a > 200) return 'Scores must be 0–200';
	if (+h === +a) return "A pick can't be a tie";
	return null;
}

export type League = 'NFL' | 'CFB';
export type PickView = { home: number; away: number };
export type GameView = {
	id: string;
	homeName: string;
	homeAbbr: string;
	awayName: string;
	awayAbbr: string;
	homeRank: number | null;
	awayRank: number | null;
	kickoffAt: string;
	status: string;
	homeScore: number | null;
	awayScore: number | null;
	spread: string | null;
	locked: boolean;
};
export type WeekView = { league: League; season: number; seasonType: number; week: number };

export const GAME_FIELDS = `id homeName homeAbbr awayName awayAbbr homeRank awayRank kickoffAt status homeScore awayScore spread locked`;

export const leagueFrom = (search: { get(k: string): string | null }): League =>
	search.get('league')?.toLowerCase() === 'cfb' ? 'CFB' : 'NFL';

export const fmtKickoff = (iso: string) =>
	new Date(iso).toLocaleString(undefined, {
		weekday: 'short',
		hour: 'numeric',
		minute: '2-digit'
	});

export const teamLabel = (name: string, rank: number | null) => (rank ? `#${rank} ${name}` : name);

export type SaveAction =
	| { kind: 'none' }
	| { kind: 'delete' }
	| { kind: 'save'; home: number; away: number }
	| { kind: 'error'; message: string };

/** What blur should do, given the inputs and the last pick known saved on the server. */
export function saveAction(home: string, away: string, saved: PickView | null): SaveAction {
	const h = home.trim();
	const a = away.trim();
	if (!h && !a) return saved ? { kind: 'delete' } : { kind: 'none' };
	const message = validatePick(h, a);
	if (message) return { kind: 'error', message };
	if (saved && saved.home === +h && saved.away === +a) return { kind: 'none' };
	return { kind: 'save', home: +h, away: +a };
}
