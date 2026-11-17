#!/bin/sh
# Build the app and upload it to TestFlight. Needs Xcode signed in to the team in the project, and an app
# record for cc.sportspicks.app in App Store Connect. The build number is the time, so every upload is newer.
set -eu
cd "$(dirname "$0")"
npm run build:app
archive="$(mktemp -d)/Pickems.xcarchive"
cd ios/App
xcodebuild -project App.xcodeproj -scheme App -configuration Release -destination 'generic/platform=iOS' \
	-archivePath "$archive" -allowProvisioningUpdates CURRENT_PROJECT_VERSION="$(date -u +%Y%m%d%H%M)" archive -quiet
xcodebuild -exportArchive -archivePath "$archive" -exportOptionsPlist ExportOptions.plist \
	-exportPath "$archive-export" -allowProvisioningUpdates
