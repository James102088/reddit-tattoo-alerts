# Reddit Tattoo Rec Alerts

Checks r/Tattoo_NYC, r/tattoos, and r/NYCbitcheswithtaste every ~10 minutes
for people asking for tattoo artist recommendations, and pushes each match to
your phone with [ntfy](https://ntfy.sh). Tap the notification to open the post.

| Subreddit | Alerts when the post… |
|---|---|
| r/Tattoo_NYC | asks for a rec / artist / shop |
| r/tattoos | asks for a rec **and** mentions NYC or a borough or neighborhood |
| r/NYCbitcheswithtaste | asks for a rec **and** mentions tattoos |

Runs free on GitHub Actions. No server, and no Reddit account needed.

## Setup (about 10 minutes)

### 1. Phone
1. Install **ntfy** (iOS App Store / Google Play).
2. Tap **+**, then subscribe to a topic name that's hard to guess, such as
   `tattoo-recs-k7x92q`. Anyone who knows the name can read it, so don't use
   anything obvious.

### 2. GitHub repo
1. Create a new repo on github.com, e.g. `reddit-tattoo-alerts`.
   - **Public is recommended:** public repos get unlimited free Actions minutes.
     A private repo running every 10 minutes would use ~4,300 of its 2,000 free
     minutes a month. To go private, change the cron in
     `.github/workflows/monitor.yml` to `*/30 * * * *`.
   - Nothing sensitive is in the code. Your ntfy topic is stored as a secret.
2. Push this folder:
   ```bash
   cd ~/Documents/reddit-tattoo-alerts
   git remote add origin https://github.com/<you>/reddit-tattoo-alerts.git
   git push -u origin main
   ```
3. In the repo, go to **Settings → Secrets and variables → Actions → New repository secret**:
   - `NTFY_TOPIC` = your topic name from step 1
4. Go to **Actions**, enable workflows if GitHub asks, then **Reddit tattoo rec monitor → Run workflow**.
   - The **first run** only records existing posts and sends no alerts, so you
     don't get flooded. Alerts start on the next run.

### Test a notification
```bash
curl -d "test from tattoo monitor" ntfy.sh/<your-topic>
```

## Tuning
Everything is in `config.json`:
- `request_patterns` are phrases that count as asking for a rec.
- `exclude_patterns` skip artist self-promo, removal or derm questions, and similar posts.
- `nyc_patterns` are the location words used to filter r/tattoos.
- To add a subreddit, add it under `subreddits`. You can give it
  `require_nyc_mention` and/or `require_tattoo_mention`.

To preview what would match right now without sending anything:
```bash
DRY_RUN=1 python3 monitor.py
```

## If Reddit blocks GitHub
Reddit sometimes blocks cloud servers' unauthenticated requests. You'd see
`fetch failed: HTTP Error 403` in the Actions log. The fix is to add Reddit API
credentials:
1. Go to https://www.reddit.com/prefs/apps, choose **create another app…**, then pick type **script**.
2. Add the repo secrets `REDDIT_CLIENT_ID` (the string under the app name) and
   `REDDIT_CLIENT_SECRET`.

The script switches to the API automatically when both are set. Reddit now
reviews new API apps, so approval may take a few days.

## Notes
- GitHub can delay scheduled runs, so alerts usually arrive within 5–20 minutes of a post.
- GitHub turns off scheduled workflows after 60 days with no repo activity. The
  bot's `seen.json` commits count as activity, so that shouldn't happen here.
- Only new **posts** are watched, not comments.
