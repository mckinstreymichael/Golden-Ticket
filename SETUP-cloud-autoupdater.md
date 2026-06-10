# Stub — cloud auto-updater setup

This makes your giveaway list refresh itself in the cloud every day, with no
computer left running. A free GitHub Actions job runs the collector on a
schedule, commits the fresh `stub-data.json`, and your phone pulls it with the
dashboard’s **Sync** button.

Nothing personal goes to the cloud: the collector only writes giveaway
*listings*. Your name/address and the autofill button live only in your browser.

-----

## What you’ll put in the repo

```
your-repo/
├─ stub_fetch.py                      # the collector
├─ sources.json                       # the feeds you want
├─ stub-data.json                     # created automatically by the first run
└─ .github/workflows/fetch-giveaways.yml   # the scheduler
```

-----

## One-time setup (about 10 minutes, all from a browser)

1. **Make a free GitHub account** if you don’t have one, then create a **new
   repository**. Keep it **Public** — the phone’s Sync button fetches the raw
   file directly, and that only works without a token on a public repo. (The
   file holds only public giveaway listings, so there’s nothing sensitive in it.)
1. **Add the files.** Use the repo’s “Add file → Upload files” button:
- Upload `stub_fetch.py` and `sources.json` to the top level.
- Create the workflow: “Add file → Create new file”, name it exactly
  `.github/workflows/fetch-giveaways.yml` (GitHub makes the folders as you
  type the slashes), and paste in the workflow file’s contents.
1. **Allow the job to commit.** In the repo: **Settings → Actions → General →
   Workflow permissions → “Read and write permissions” → Save.** Without this
   the job can fetch but can’t save the result back.
1. **Edit `sources.json`** to list the feeds you actually want. Each entry is
   one of: `reddit` (a subreddit), `rss` (a feed URL), `csv` (a sheet you
   upload), or `html` (a permitted page with CSS selectors). Set `"enabled": false` to keep one in the file but skip it.
1. **Run it once by hand** to create `stub-data.json`: open the **Actions** tab,
   pick **Fetch giveaways**, click **Run workflow**. After it finishes (a minute
   or two), refresh the repo — `stub-data.json` should be there.
1. **Grab the raw URL.** Click `stub-data.json` in the repo, then the **Raw**
   button. Copy that address. It looks like:
   `https://raw.githubusercontent.com/<you>/<repo>/main/stub-data.json`

After this, the job re-runs on its own (default: once a day). You don’t touch
GitHub again unless you want to change sources.

-----

## On your iPhone

1. Put `stub-giveaway-desk.html` in the **Files** app and open it in **Safari**
   (tap the file → it opens in a browser tab). Add to Home Screen if you like.
1. On the **Tickets** tab, paste your **Raw URL** into the **Sync** box and tap
   **Sync now**. New giveaways appear; anything you’ve marked entered/won stays.
1. Tap **Sync now** whenever you want the latest. The job already gathered them
   overnight, so this is instant.
1. Use **Export** every so often to save a backup to Files (this also remembers
   your Sync URL, so re-importing restores it).

If Safari ever blocks the Sync fetch, fall back to: open the Raw URL, save the
JSON to Files, then use the dashboard’s **Import** button.

-----

## Changing the schedule

In `fetch-giveaways.yml`, edit the cron line. It’s in UTC.

```
- cron: "17 13 * * *"     # daily ~13:17 UTC
- cron: "17 */6 * * *"    # every 6 hours
- cron: "17 13 * * 1"     # Mondays only
```

GitHub sometimes delays scheduled runs during busy periods; that’s normal for
the free tier. You can always hit **Run workflow** for an immediate refresh.

-----

## Running it locally instead (optional)

On a computer: `pip install feedparser requests beautifulsoup4` then
`python3 stub_fetch.py`. On an iPhone you can use the free **a-Shell** app the
same way (the dependencies are all pure-Python, so they install fine) — but the
cloud job is the hands-off option, since iOS suspends background apps.

-----

## A note on sources

This collector reads public feeds and, for `html` sources, checks the site’s
`robots.txt` first and skips anything disallowed. If a site you want has no feed
and disallows scraping, the right move is to ask them for feed/API access rather
than work around it. Keeping the collector well-behaved is the whole point.