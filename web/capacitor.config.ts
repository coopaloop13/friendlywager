import type { CapacitorConfig } from '@capacitor/cli';

// The store apps: the built web app (npm run build:app) inside a native shell.
// The API allows exactly the origins these shells load from (APP_ORIGINS in api/app/main.py).
const config: CapacitorConfig = {
	appId: 'cc.sportspicks.app',
	appName: "Pick'ems",
	webDir: 'build',
	plugins: { FirebaseMessaging: { presentationOptions: ['alert', 'sound'] } },
	// avoids a Swift package name clash between the Firebase plugin and the Firebase SDK
	experimental: { ios: { spm: { packageOptions: { '@capacitor-firebase/messaging': { symlink: true } } } } }
};

export default config;
