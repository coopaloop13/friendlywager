import { defineEnvVars } from '@sveltejs/kit/env';

export const variables = defineEnvVars({
	API_URL: { schema: (v) => v ?? 'http://api:8000' }
});
