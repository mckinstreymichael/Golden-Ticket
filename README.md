# Stub — giveaway desk

A personal giveaway tracker. A scheduled cloud job collects giveaway listings
from public feeds, and a home-screen web app lets you review and enter them
yourself (it assists with form-filling but never submits for you).

## Repo layout

```
.
├─ index.html                          # the app (open this in a browser / install to Home Screen)
├─ manifest.json                       # makes it installable as an app
├─ icon-180.png  icon-192.png  icon-512.png   # app icons
├─ stub_fetch.py                       # the read-only collector
├─ sources.json                        # the feeds it pulls from (edit this)
├─ stub-data.json                      # created automatically by the first job run
├─ fill-test.html                      # optional sandbox to test the autofill bookmark
└─ .github/
   └─ workflows/
      └─ fetch-giveaways.yml           # the daily scheduler  (NOTE the folder path)
```

The single most important placement detail: **`fetch-giveaways.yml` must live at
`.github/workflows/fetch-giveaways.yml`** or GitHub won’t run it. When uploading,
use “Add file → Create new file” and type that full path including the slashes;
GitHub creates the folders for you.

## Setup, in order

1. Upload all the files above (keep the workflow at its `.github/workflows/` path).
1. **Settings → Actions → General → Workflow permissions → Read and write → Save**
   (lets the job commit the refreshed list).
1. **Settings → Pages → Deploy from a branch → main → /(root) → Save** to host the
   app. Note the URL it gives you (`https://<you>.github.io/<repo>/`).
1. **Actions tab → Fetch giveaways → Run workflow** once to create `stub-data.json`.
1. On your iPhone, open the Pages URL in **Safari → Share → Add to Home Screen**.
1. In the app’s Sync box, paste `https://<you>.github.io/<repo>/stub-data.json`.

Keep the repo **public** so the app can fetch `stub-data.json` without a token.
The committed file holds only public giveaway listings — your name, address, and
autofill details stay on your device, never in the repo.

Full walkthroughs: `SETUP-cloud-autoupdater.md` (the cloud job) and
`INSTALL-as-app.md` (the Home Screen app).

## What it does and doesn’t do

- It **collects** listings from feeds you choose and **assists** you in filling
  entry forms (you review and submit each one).
- It does **not** auto-enter giveaways, submit forms, create accounts, or bypass
  captchas/verification. HTML sources are fetched only if the site’s robots.txt
  permits it.