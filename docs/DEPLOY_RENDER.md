# Putting SpectralTurf AI online with Render

This guide puts the website on the internet with [Render](https://render.com). Everything is
already prepared in the code. You only click through Render's website and paste your keys.
Running the app on your own computer works exactly as before.

**What you'll end up with**
- `https://spectralturf-frontend.onrender.com`: the website people open.
- `https://spectralturf-backend.onrender.com`: the Python server. People never open it directly.
  The website forwards everything under `/api/...` to it.

**What it costs.** The website (static site) is free. The backend needs Render's smallest
**paid** instance (starting around $7/month; check Render's pricing page). The reason is the
persistent disk: it keeps accounts and saved fields. On the free plan, every restart wipes
them, and the free server falls asleep after 15 minutes without visitors.

---

## Before you start (checklist)

1. All the code is on GitHub (`git push`). Render reads it from there.
2. You have these 3 secrets ready. They are in your `backend/.env`. Open that file yourself,
   and never paste the keys into chat, an issue or a commit.
   - `CDSE_CLIENT_ID` and `CDSE_CLIENT_SECRET` (Copernicus)
   - `GEMINI_API_KEY` (Google Gemini)
3. A Render account. Sign up at render.com with your GitHub account. Render will ask to see
   your repositories; allow access to `SpectralTurf` only.

## Step 1: Create both services from the Blueprint

1. In Render, click **New → Blueprint**.
2. Choose the `SpectralTurf` repository. Render finds `render.yaml` and shows 2 services:
   `spectralturf-backend` and `spectralturf-frontend`.
3. Render asks for the 3 secrets (`CDSE_CLIENT_ID`, `CDSE_CLIENT_SECRET`, `GEMINI_API_KEY`).
   Paste each value from your `.env`, with no quotes and no spaces.
4. Check the price summary (the backend is a paid instance with a 1 GB disk), then click
   **Apply** / **Deploy Blueprint**.
5. Wait for both to show **Live**. The backend's first build takes a few minutes because it
   installs numpy and scikit-learn.

## Step 2: Check the backend's address

1. Open `spectralturf-backend` in Render. At the top is its address, for example
   `https://spectralturf-backend.onrender.com`.
2. Open that address + `/api/health` in your browser. You should see `{"status":"ok"}`.
3. **If the address is different** (Render adds letters when a name is taken, e.g.
   `spectralturf-backend-x7k2.onrender.com`):
   - open `render.yaml`, change the `destination:` line under `/api/*` to the real address
     (keep `/api/*` on the end);
   - then commit and push. Render redeploys the website by itself.

## Step 3: Test the website

Open the frontend address (`https://spectralturf-frontend.onrender.com`) and check:

| Test | What success looks like |
|---|---|
| Page loads | Map of Colorado, sidebar panels |
| Search "Village Greens", draw a field, **Analyze** | Real NDVI/NDMI with an image date, the same numbers as on your computer |
| Make an account, log in, log out, log in again | Works; the analysis appears under "Your account" |
| **Restart** the backend (Render → backend → Manual Deploy → Restart) | You're still able to log in and your saved fields are still there (the disk works) |
| AI Weather Check, What if?, My Fields | Same kind of answers as locally |
| Ask SpectralTurf: press a preset question | An answer with "AI-generated explanation…" |
| Type a wrong password 5 times | "Too many wrong passwords for this username… wait 15 minutes" |

If **everything** says "HTTP 404" or "could not reach the backend", the `/api/*` rewrite
address is wrong (see Step 2). If the AI says it isn't set up, check `GEMINI_API_KEY` on the
backend's **Environment** page.

## The safety limits (on automatically on Render)

These protect your free Copernicus and Gemini quotas from being used up by one person or a
bot. They are project choices, not standards. When a limit is reached, people see a friendly
message. The code is in `backend/limits.py`.

| What | Each logged-in user / day | Each visitor (by internet address) / day | Whole website / day |
|---|---|---|---|
| New satellite analyses | 30 | 10 | 300 |
| AI checks (weather check, What if?, My Fields) | 200 | 100 | 2,000 |
| Ask SpectralTurf messages | 40 | 15 | 300 |
| New accounts | – | 5 | 100 |

The older limits still apply on top of these: 5 chat messages per minute, and the AI checks'
own budget of 100 Copernicus processing units per day.

- **Wrong passwords:** 5 wrong passwords for one username within 15 minutes locks that username
  for 15 minutes. 20 from one internet address locks that address. Downside: someone could
  lock a friend out for 15 minutes on purpose. That is the usual trade-off.
- **"Per day"** follows the server clock (UTC). In Colorado the counts reset at 5 pm (winter)
  or 6 pm (summer).
- **Visitors are told apart by internet address.** A whole school on one Wi-Fi shares one
  address, and a determined person can fake theirs. The whole-website limits are what really
  protect your quotas.
- **To change a number,** add an environment variable on the backend's **Environment** page,
  e.g. `LIMIT_ANALYSES_TOTAL` = `150`. Render restarts the backend. All the names are at the
  top of `backend/limits.py`.
- **To test the limits on your own computer:** start the backend with
  `$env:USAGE_LIMITS="on"` set first. Normally they are off locally.

Also keep an eye on your real quotas from time to time:
- Copernicus dashboard: processing units used this month.
- Google AI Studio: Gemini usage.

## Things to know

- **Privacy / Gemini.** On Gemini's free tier, Google may use what is sent to improve its
  products. The chat panel already warns people not to type personal information or send
  photos of people. Questions, field numbers and photos are sent; usernames, field names and
  map locations are not.
- **Users are probably students.** Accounts need only a username and password (no email), and
  there is no "forgot password". Tell testers to pick a password they don't use anywhere else.
- **Backups.** Render takes a snapshot of the disk every 24 hours and keeps it 7 days.
- **Deploys** briefly stop the backend (about a minute) because a disk is attached. Avoid
  deploying during a demo.
- **Only one backend copy can run** (the disk belongs to one instance). That is plenty for this
  project.
- **Esri map photos.** Before a big public launch, check Esri's terms for the World Imagery
  basemap (listed as unverified in the README).

## What was changed in the code for this (all add-ons)

- `render.yaml`: the Blueprint (new).
- `backend/limits.py` + the end of `backend/main.py`: login lockout and daily limits (new).
  These are only on when `RENDER` is set (Render does this automatically) or `USAGE_LIMITS=on`.
- `backend/accounts.py`: the database location can be set with `DATABASE_PATH`. Not set means
  the same `backend/spectralturf.db` as before.
- `backend/predict.py`: the AI cache location can be set with `AI_CACHE_DIR`. Not set means
  `backend/ai_cache` as before.
- `backend/requirements.txt`: added `joblib` and `scikit-learn==1.9.1`. The AI model needs
  them, and they were missing, so a fresh install would have failed. scikit-learn is pinned to
  the version the model was saved with.
- The website already called the backend at `/api/...` (no `localhost` address in the built
  site), so the frontend needed no change.
- Tests: `backend/test_limits.py`.

**Files the app needs on the server:** these are all in git already. They are the trained
model (`ml/model/ndvi_model_v3.joblib`, plus `ndvi_model.joblib` as backup), the code it loads
(`ml/train.py`, `ml/train_v3.py`, `ml/build_dataset.py`, `ml/build_dataset_v3.py`,
`ml/get_ndvi_history.py`) and the weather history for the What-if month limits
(`ml/data/weather/*.csv`, 1.7 MB). The raw download caches (`ml/data/cache/`,
`backend/ai_cache/`), `.env` and the database are **not** in git, and the app doesn't need them.

## If something goes wrong

- **The build fails installing Python packages.** Open the backend's **Logs**. If Render
  doesn't have Python 3.13.14, change `PYTHON_VERSION` in `render.yaml` to the newest `3.13.x`
  Render lists, then push.
- **The website build says the publish folder `dist` isn't found.** In `render.yaml`, change
  `staticPublishPath: dist` to `staticPublishPath: frontend/dist`, then push.
- **"Copernicus login failed"** means the two CDSE values on the backend's Environment page are
  wrong (extra space?).
- **The backend keeps restarting.** Check the Logs for the error. Never paste the logs anywhere
  public before checking that they contain no keys. The app never prints them.
