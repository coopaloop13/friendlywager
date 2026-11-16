import { Container, getContainer } from "@cloudflare/containers";

// Worker secrets (`wrangler secret put`); not in wrangler.jsonc so not in generated Env.
declare global {
	interface Env {
		DATABASE_URL: string;
		SESSION_SECRET: string;
		SYNC_SECRET: string;
		EMAIL_API_TOKEN: string;
		CLOUDFLARE_ACCOUNT_ID: string;
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
			SYNC_SECRET: env.SYNC_SECRET,
			EMAIL_API_TOKEN: env.EMAIL_API_TOKEN,
			CLOUDFLARE_ACCOUNT_ID: env.CLOUDFLARE_ACCOUNT_ID,
			COOKIE_SECURE: "true",
		};
	}
}

// One named instance serves everything (single SQL-backed app, ~friends scale).
const api = (env: Env) => getContainer(env.API, "main");

const tooMany = () =>
	Response.json(
		{ errors: [{ message: "Too many requests. Give it a minute.", extensions: { code: "RATE_LIMITED" } }] },
		{ status: 429 },
	);

export default {
	async fetch(req: Request, env: Env) {
		if (new URL(req.url).pathname === "/graphql" && req.method === "POST") {
			// Direct callers get their real IP here; the web proxy passes the visitor's (see web/src/routes/graphql).
			const key = req.headers.get("cf-connecting-ip") ?? "unknown";
			if (!(await env.GQL_LIMIT.limit({ key })).success) return tooMany();
			// Each code request sends an email, so it gets a much smaller budget. A field name can't be
			// escaped in GraphQL, so the substring is enough; the API caps the body at 16 KB.
			const asksForCode = (await req.clone().text()).includes("requestLoginCode");
			if (asksForCode && !(await env.CODE_LIMIT.limit({ key })).success) return tooMany();
		}
		return api(env).fetch(req);
	},

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
