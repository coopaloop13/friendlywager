export const NAME = "Pick'ems";
export const FULL_NAME = "Pick'ems: Box Score Picks";
/** Must be a mailbox someone reads: it is the contact in the terms and privacy pages and the report link. */
export const SUPPORT = 'support@sportspicks.cc';
export const reportHref = `mailto:${SUPPORT}?subject=${encodeURIComponent("Pick'ems report")}`;
/** Where the store apps reach the site and the API; the web app uses its own origin and the /graphql proxy. */
export const SITE = 'https://sportspicks.cc';
export const API = 'https://api.sportspicks.cc';
