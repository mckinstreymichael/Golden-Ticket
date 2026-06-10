# Put Stub on your iPhone Home Screen (as an app)

This turns the dashboard into a real app: its own gold-ticket icon, opens full
screen with no Safari bars, and now **remembers your data between launches**.

The icon and standalone mode need the files served from a web address, so the
clean path is GitHub Pages — and you likely already have the repo from the
cloud auto-updater. Pages is free.

## Files this app uses

Put these four in your repo (top level is simplest):

```
index.html        <- rename stub-giveaway-desk.html to this
manifest.json
icon-180.png
icon-192.png
icon-512.png
```

(Renaming to `index.html` gives you a clean URL with no filename on the end.)

## Turn on GitHub Pages (one time)

1. Upload the files to your repo (Add file -> Upload files).
1. Repo **Settings -> Pages**.
1. Under “Build and deployment”, Source = **Deploy from a branch**, Branch =
   **main**, folder = **/(root)**, then **Save**.
1. Wait ~1 minute, refresh. Pages shows your live URL, like
   `https://<you>.github.io/<repo>/`. Open it once in any browser to confirm it
   loads.

## Install it on the iPhone

1. Open that Pages URL in **Safari** (must be Safari, not Chrome, for install).
1. Tap the **Share** button (square with the up arrow).
1. Scroll down, tap **Add to Home Screen**, then **Add**.
1. You’ll get a “Stub” icon on your Home Screen. Tapping it opens full screen,
   no address bar — it behaves like an app.

## First launch

- Go to the **Tickets** tab, paste your `stub-data.json` raw URL into **Sync**,
  tap **Sync now**. (If you host the JSON in the same repo, the URL is
  `https://<you>.github.io/<repo>/stub-data.json`.)
- From now on the app remembers your giveaways, statuses, profile, and sync URL
  between launches. Tap **Sync now** whenever you want the cloud’s latest; your
  entered/won marks are preserved.

## Notes

- **Updating the app:** when you change `index.html` in the repo, the installed
  app picks up the new version next time it loads (you may need to close and
  reopen it). No reinstall needed.
- **Your data stays on the phone.** Persistence uses the browser’s local storage
  on your device; nothing about your profile is uploaded. Keep using **Export**
  for an occasional backup to Files.
- **Android/desktop:** the same hosted URL installs as an app there too
  (Chrome: menu -> Install app / Add to Home screen).