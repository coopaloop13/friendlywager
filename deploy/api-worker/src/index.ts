import { Container, getContainer } from "@cloudflare/containers";

// Worker secrets (`wrangler secret put`); not in wrangler.jsonc so not in generated Env.
declare global {
	interface Env {
		DATABASE_URL: string;
		SESSION_SECRET: string;
		INVITE_CODE: string;
		SYNC_SECRET: string;
	}
}

export class Api extends Container<Env> {
	defaultPort = 8000;
	sleepAfter = "10m";
	envVars: Record<string, string>;

	constructor(ctx: DurableObjectState<{}>, env: Env) {
		super(ctx, env);
		this.envVars = {
			DATABASE_URL: env.DATABASE_URL,
			SESSION_SECRET: env.SESSION_SECRET,
			INVITE_CODE: env.INVITE_CODE,
			SYNC_SECRET: env.SYNC_SECRET,
			COOKIE_SECURE: "true",
		};
	}
}

// One named instance serves everything (single SQL-backed app, ~friends scale).
const api = (env: Env) => getContainer(env.API, "main");

export default {
	fetch: (req: Request, env: Env) => api(env).fetch(req),

	async scheduled(_c: ScheduledController, env: Env) {
		const res = await api(env).fetch(
			new Request("http://api/internal/sync", {
				method: "POST",
				headers: { "X-Sync-Secret": env.SYNC_SECRET },
			}),
		);
		if (!res.ok) throw new Error(`sync failed: ${res.status} ${(await res.text()).slice(0, 500)}`);
	},
} satisfies ExportedHandler<Env>;
