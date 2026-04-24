<div align="center">

<img src="assets/Smart_Pick_Pro_Logo.png" alt="Smart Pick Pro" width="180" />

# Smart Pick Pro

### AI-Powered NBA Prop Betting Intelligence

[![Python 3.11–3.13](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue?logo=python&logoColor=white)](#python-requirements)
[![Streamlit](https://img.shields.io/badge/built%20with-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](#)
[![License](https://img.shields.io/badge/license-proprietary-333)](#)

**Real-time prop analysis across PrizePicks · Underdog Fantasy · DraftKings Pick6**

*Quantum Matrix Engine 5.6 simulation • Multi-model ML ensemble • Live in-game tracking*

---

</div>

## What It Does

Smart Pick Pro is a locally-run Streamlit web app that ingests live NBA data, simulates thousands of game outcomes per prop, and surfaces the highest-edge bets with a four-tier confidence system (**Platinum 💎 → Gold 🥇 → Silver 🥈 → Bronze 🥉**). Everything runs on your machine — no cloud dependency, no monthly API fees for core functionality.

| Capability | How |
|---|---|
| **Prop simulation** | Quantum Matrix Engine 5.6 — Quantum sim (1k–5k iterations) with directional force analysis |
| **Machine learning** | XGBoost + CatBoost + Ridge ensemble with 6-step feature pipeline |
| **Live tracking** | In-game pace projections, sweat cards, Joseph M. Smith AI commentary |
| **Entry building** | Optimal parlay construction with EV-maximized combinatorics |
| **Bet tracking** | Auto-resolve against box scores, model health monitoring, bankroll tools |
| **Data pipeline** | ETL into local SQLite (39 tables), incremental updates, injury report parsing |

---

## Pages at a Glance

| # | Page | Purpose |
|---|------|---------|
| 🏠 | **Home** | Dashboard — tonight's slate, status, quick-start workflow |
| 💦 | **Live Sweat** | AI Panic Room — real-time bet tracking with pace projections |
| 📡 | **Live Games** | One-Click Setup — load games, rosters, live platform props |
| 🔬 | **Prop Scanner** | Manual entry, CSV upload, or live platform line fetch |
| ⚡ | **Quantum Analysis Matrix** | Main engine — simulation, edge detection, tier ranking |
| 📋 | **Game Report** | AI game reports with SAFE Score™ and entry strategy matrix |
| 🔮 | **Player Simulator** | What-if scenario modeling (minutes, pace, matchup sliders) |
| 🧬 | **Entry Builder** | Optimal DFS parlays across platform payout structures |
| 🎙️ | **The Studio** | Joseph M. Smith's broadcast desk — game breakdowns, scout, bet builder |
| 🛡️ | **Risk Shield** | Flagged props with risk explanations (trap lines, sharp action, variance) |
| 📡 | **Smart NBA Data** | Stats hub — player/team stats, leaders, standings, playoff picture |
| 🗺️ | **Correlation Matrix** | Prop correlation analysis for smarter parlays |
| 📈 | **Bet Tracker** | Log & resolve bets, model health, performance predictor, bankroll |
| 📊 | **Proving Grounds** | Historical backtesting with tier-by-tier ROI metrics |
| ⚙️ | **Settings** | Sim depth, edge thresholds, preset profiles, API keys |
| 💎 | **Subscription** | Premium tier management (Stripe) |

---

## Quick Start

### Python Requirements

| Version | Status |
|---------|--------|
| **3.11** | ✅ Recommended |
| **3.12** | ✅ Supported |
| **3.13** | ✅ Supported |
| **3.14+** | ❌ Not supported — missing pre-built wheels for pandas/numpy/catboost |
| **≤ 3.10** | ❌ Missing required language features |

### Install & Run

```bash
# 1. Clone / download the repo and cd into it

# 2. Create & activate a virtual environment
python -m venv .venv

# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Bootstrap the database (first run only — pulls 2025-26 season data)
python bootstrap.py

# 5. Launch
streamlit run Smart_Picks_Pro_Home.py
```

> **Windows note:** If PowerShell says "running scripts is disabled", run this first:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

The app opens at **http://localhost:8501**.

### First Session Workflow

1. **⚙️ Settings** — enter API keys (Odds API, API-NBA) if you have them
2. **📡 Smart NBA Data** → **Smart Update** — fetch tonight's player/team data
3. **📡 Live Games** → **⚡ One-Click Setup** — load matchups + live platform props
4. **⚡ Quantum Analysis Matrix** → **Run Analysis** — simulate and rank every prop

### Daily Workflow

```bash
# Activate venv, launch app
.venv\Scripts\Activate.ps1        # or: source .venv/bin/activate
streamlit run Smart_Picks_Pro_Home.py
```

Then in browser: **Live Games → One-Click Setup → Quantum Analysis Matrix → Run Analysis** → review picks.

---

## Docker (Alternative)

```bash
cp .env.example .env               # edit with your API keys
docker compose up --build
```

UI on **:8501**, FastAPI on **:8000**, Caddy reverse proxy on **:80/:443**.

---

## Architecture

```
Smart Pick Pro/
│
├─ Smart_Picks_Pro_Home.py          # Entry point — home dashboard
├─ bootstrap.py                     # First-run ETL bootstrap
├─ webhook_server.py                # Stripe webhook server
│
├─ pages/                           # 15 Streamlit pages
│  ├─ 0  Live Sweat                 #   Live AI Panic Room
│  ├─ 1  Live Games                 #   Tonight's games + one-click setup
│  ├─ 2  Prop Scanner               #   Prop entry / upload / fetch
│  ├─ 3  Quantum Analysis Matrix    #   Main simulation engine
│  ├─ 4  Game Report                #   SAFE Score AI reports
│  ├─ 5  Player Simulator           #   What-if scenario modeling
│  ├─ 6  Entry Builder              #   Optimal DFS parlays
│  ├─ 7  The Studio                 #   Joseph M. Smith broadcast desk
│  ├─ 8  Risk Shield                #   Flagged props & risk analysis
│  ├─ 9  Smart NBA Data             #   Stats hub & data management
│  ├─ 10 Correlation Matrix         #   Prop correlation analysis
│  ├─ 11 Bet Tracker                #   Bet logging & model health
│  ├─ 12 Proving Grounds            #   Historical backtesting
│  ├─ 13 Settings                   #   Engine configuration
│  ├─ 14 Subscription               #   Premium tier (Stripe)
│  └─ helpers/                      #   Tab modules & shared logic
│     └─ bet_tracker_tabs/          #   11 Bet Tracker tab modules
│
├─ engine/                          # Core math & ML
│  ├─ simulation.py                 #   QME 5.6 Quantum simulator
│  ├─ projections.py                #   Player stat projections
│  ├─ edge_detection.py             #   Edge + directional force analysis
│  ├─ confidence.py                 #   Confidence scoring + tier system
│  ├─ ensemble.py                   #   Multi-model combiner
│  ├─ models/                       #   XGBoost, CatBoost, Ridge
│  ├─ pipeline/                     #   6-step ML pipeline
│  ├─ predict/                      #   Prediction engine
│  ├─ features/                     #   Feature engineering
│  ├─ scrapers/                     #   BBRef, CBS, transactions
│  └─ joseph_brain/                 #   Joseph M. Smith AI persona
│
├─ data/                            # Data access layer
│  ├─ nba_data_service.py           #   NBA data orchestration
│  ├─ platform_fetcher.py           #   PrizePicks / Underdog / DK fetcher
│  ├─ live_data_fetcher.py          #   Live enrichment
│  ├─ roster_engine.py              #   Rosters & injury tracking
│  └─ db_service.py                 #   SQLite gateway
│
├─ etl/                             # ETL pipeline → smartpicks.db
│  ├─ setup_db.py                   #   39-table schema
│  ├─ initial_pull.py               #   Full historical pull
│  └─ data_updater.py               #   Incremental updates
│
├─ tracking/                        # Bet logging & model metrics
│  ├─ bet_tracker.py                #   Bet CRUD + auto-resolve
│  ├─ database.py                   #   SQLite wrapper
│  └─ model_performance.py          #   Performance tracking
│
├─ api/                             # REST API (FastAPI + Uvicorn)
├─ agent/                           # Live commentary persona engine
├─ config/                          # Thresholds & settings
├─ styles/                          # Global CSS + Live Sweat theme
├─ utils/                           # Shared components & helpers
├─ db/                              # SQLite databases
└─ scripts/                         # Utility scripts
```

---

## How the Engine Works

### Quantum Matrix Engine 5.6

For each prop, the engine runs **1,000–5,000 Quantum simulations**:

1. **Minutes** — randomized with variance (rest days, foul trouble, blowouts)
2. **Stats** — drawn from a normal distribution centered on the projected line, shaped by directional forces (matchup, pace, home/away, injury context, recent form)
3. **Tally** — count OVER vs UNDER outcomes

```
probability = games_over / total_simulations
edge       = probability - implied_probability
```

### Confidence Tiers

| Tier | Badge | Criteria |
|------|-------|----------|
| **Platinum** | 💎 | Edge ≥ 12%, confidence ≥ 80 |
| **Gold** | 🥇 | Edge ≥ 8%, confidence ≥ 65 |
| **Silver** | 🥈 | Edge ≥ 5%, confidence ≥ 50 |
| **Bronze** | 🥉 | Below Silver thresholds |

### ML Ensemble

Three models vote on each prop:

| Model | Type | Strength |
|-------|------|----------|
| **XGBoost** | Gradient boosted trees | Handles non-linear feature interactions |
| **CatBoost** | Ordered boosting | Native categorical feature support |
| **Ridge** | Regularized linear | Stable baseline, prevents overfitting |

The ensemble output feeds into the simulation as a projection adjustment, not a replacement.

### Expected Value (EV)

For parlay construction:

$$EV = \sum P(\text{outcome}) \times \text{payout} - \text{entry fee}$$

Positive EV = profitable in the long run. The Entry Builder tests all top-pick combinations and ranks by EV.

---

## Data Sources

| Data | Source | Storage |
|------|--------|---------|
| Player season stats | `nba_api` + API-NBA | `db/smartpicks.db` |
| Team pace / ORTG / DRTG | `nba_api` + API-NBA | `db/smartpicks.db` |
| Player game logs | `nba_api` | `db/smartpicks.db` |
| Tonight's games + lines | API-NBA + Odds API | Session state |
| Live platform props | PrizePicks / Underdog / DK | Session state |
| Defensive ratings | Calculated from DRTG | `data/defensive_ratings.csv` |
| Injury reports | NBA official PDF + CBS / Rotowire | Parsed on demand |

---

## Dependencies

### Core

| Package | Purpose |
|---------|---------|
| `streamlit` | Web UI framework |
| `streamlit-autorefresh` | Auto-refresh for live pages |
| `pandas` / `numpy` | Data manipulation & numerical computing |
| `requests` / `aiohttp` | Sync & async HTTP |

### Machine Learning

| Package | Purpose |
|---------|---------|
| `scikit-learn` | Ridge regression |
| `xgboost` | Gradient boosted trees |
| `catboost` | Ordered boosting ensemble |
| `joblib` | Model serialization |

### Data & Parsing

| Package | Purpose |
|---------|---------|
| `nba_api` | NBA.com stats client |
| `beautifulsoup4` / `lxml` | Web scraping |
| `pdfplumber` | Injury report PDF parsing |
| `pyarrow` | Parquet I/O |
| `thefuzz` | Fuzzy player name matching |

### API & Infrastructure

| Package | Purpose |
|---------|---------|
| `fastapi` / `uvicorn` | REST API |
| `flask` | Stripe webhook server |
| `stripe` | Payment processing |
| `python-dotenv` | Environment variable management |

---

## Production Deployment

### Streamlit Community Cloud

1. Push to GitHub
2. Connect at [share.streamlit.io](https://share.streamlit.io)
3. Add secrets in **Settings → Secrets** (see `.streamlit/secrets.toml.example`)
4. Set `SMARTAI_PRODUCTION=true` and `APP_URL`

### Docker

```bash
cp .env.example .env && docker compose up --build -d
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ODDS_API_KEY` | For DK props | The Odds API key |
| `STRIPE_SECRET_KEY` | For payments | Stripe secret key |
| `STRIPE_PUBLISHABLE_KEY` | For payments | Stripe publishable key |
| `STRIPE_PRICE_ID` | For payments | Stripe product price ID |
| `STRIPE_WEBHOOK_SECRET` | Recommended | Webhook signing secret |
| `SMARTAI_PRODUCTION` | Production | `"true"` to enforce subscription gates |
| `APP_URL` | Production | Deployed app URL |
| `DB_PATH` | Optional | Override SQLite path |
| `LOG_LEVEL` | Optional | DEBUG / INFO / WARNING / ERROR |

### Stripe Webhook Setup

1. Deploy `webhook_server.py` to a hosting platform (Railway, Render, Fly.io)
2. In Stripe Dashboard → Developers → Webhooks, register your URL
3. Select events: `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`
4. Copy the signing secret (`whsec_...`) → add as `STRIPE_WEBHOOK_SECRET`

---

## Troubleshooting

<details>
<summary><strong>pip install fails — "metadata-generation-failed" or Meson build error</strong></summary>

You're on Python 3.14+. Downgrade to 3.11 or 3.12 and recreate the venv.

</details>

<details>
<summary><strong>"streamlit: command not found"</strong></summary>

Make sure the venv is activated (`(.venv)` in prompt). Or use: `python -m streamlit run Smart_Picks_Pro_Home.py`

</details>

<details>
<summary><strong>"ModuleNotFoundError"</strong></summary>

Run `pip install -r requirements.txt` inside the activated venv.

</details>

<details>
<summary><strong>Port 8501 already in use</strong></summary>

```bash
streamlit run Smart_Picks_Pro_Home.py --server.port 8502
```

</details>

<details>
<summary><strong>PowerShell "running scripts is disabled"</strong></summary>

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

</details>

<details>
<summary><strong>Live data update takes a long time</strong></summary>

Normal — the fetcher throttles API calls at 1.5s intervals to avoid rate limits. Full updates take 5–15 minutes.

</details>

<details>
<summary><strong>App shows "No props loaded"</strong></summary>

Go to **Live Games → One-Click Setup** or manually enter props on the Prop Scanner page.

</details>

---

## Running Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

---

## Disclaimer

This app is for **personal entertainment and analysis** only. Always gamble responsibly. Past model performance does not guarantee future results. Never bet more than you can afford to lose.

**Responsible Gambling:** If you or someone you know has a gambling problem, call **1-800-522-4700** or visit [ncpgambling.org](https://www.ncpgambling.org).
# 🏀 Smart Pick Pro v7

**Your Personal NBA Prop Betting Analysis Engine — Built Locally, No APIs Needed**

Smart Pick Pro v7 is a local web app (Streamlit) that analyzes PrizePicks, Underdog Fantasy,
and DraftKings Pick6 props to find the highest-probability bets using Quantum Matrix Engine 5.6 simulation
and directional force analysis. All math is built from scratch — no external libraries except Streamlit.

---

## 🐍 Supported Python Versions

| Python Version | Status |
|----------------|--------|
| **3.11** | ✅ Fully supported — **recommended** |
| **3.12** | ✅ Fully supported |
| **3.13** | ✅ Supported |
| **3.14+** | ❌ **Not supported** — many packages (pandas, numpy, catboost, etc.) do not have pre-built wheels yet. You will get build errors. |
| **3.9 and below** | ❌ Not supported — missing required language features |

> **⚠️ If you are on Python 3.14:** You MUST downgrade. See [Step 1](#step-1-install-python) below.

---

## 🚀 Quick Start (Complete Beginner Guide)

Follow every step below **in order**. Do not skip any steps.

### Step 1: Install Python

You need **Python 3.11 or 3.12** (recommended). Python 3.13 also works. **Do NOT use Python 3.14** — it will fail.

#### How to check if Python is already installed

Open a terminal and try **all three** commands below. At least one should work:

| Command | When it works |
|---------|---------------|
| `python --version` | Most Windows installs, some Mac/Linux |
| `python3 --version` | Most Mac and Linux installs |
| `py --version` | Windows Python Launcher (installed with Python on Windows) |

You should see output like `Python 3.11.9` or `Python 3.12.4`.

> **💡 Which command worked for you?** Remember it — you'll use that same command prefix throughout this guide.
> For example, if `python3 --version` worked, you'll use `python3` everywhere below.

#### If Python is not installed (or you need to downgrade from 3.14)

<details>
<summary><strong>🪟 Windows</strong></summary>

1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Download **Python 3.12.x** (click the yellow "Download Python 3.12.x" button)
3. Run the installer
4. **✅ IMPORTANT:** Check the box that says **"Add python.exe to PATH"** at the bottom of the first screen
5. Click **"Install Now"**
6. After installation, **close and reopen** your terminal (PowerShell or Command Prompt)
7. Verify: run `python --version` or `py --version` — you should see `Python 3.12.x`

> **Already have Python 3.14 installed?** You can install 3.12 alongside it. Use `py -3.12` to specifically use Python 3.12:
> ```powershell
> py -3.12 --version       # Should show Python 3.12.x
> py -3.12 -m venv .venv   # Create venv with Python 3.12
> ```

</details>

<details>
<summary><strong>🍎 macOS</strong></summary>

**Option A — Homebrew (recommended if you have Homebrew):**
```bash
brew install python@3.12
```

**Option B — Official installer:**
1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Download **Python 3.12.x** for macOS
3. Run the `.pkg` installer
4. After installation, close and reopen your terminal
5. Verify: `python3 --version` should show `Python 3.12.x`

</details>

<details>
<summary><strong>🐧 Linux (Ubuntu / Debian)</strong></summary>

```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip
```

Verify: `python3.12 --version` should show `Python 3.12.x`

</details>

---

### Step 2: Open a Terminal

| Operating System | How to open a terminal |
|------------------|------------------------|
| **Windows** | Press `Win + R`, type `powershell`, press Enter. Or search "PowerShell" in the Start menu. |
| **macOS** | Press `Cmd + Space`, type `Terminal`, press Enter. |
| **Linux** | Press `Ctrl + Alt + T`, or search "Terminal" in your applications. |

---

### Step 3: Navigate to the App Folder

Use the `cd` command to go to the folder where you downloaded/extracted Smart Pick Pro.

**Windows examples:**
```powershell
cd "C:\Users\YourName\Downloads\Smart Pick Pro"
# or
cd "$env:USERPROFILE\Documents\Smart Pick Pro"
```

**Mac / Linux examples:**
```bash
cd ~/Downloads/"Smart Pick Pro"
# or
cd ~/Documents/"Smart Pick Pro"
```

> **💡 Tip:** You can drag the folder from File Explorer / Finder into the terminal window to paste the full path.

---

### Step 4: Create a Virtual Environment (Recommended)

A virtual environment keeps this project's packages separate from your system Python. This prevents version conflicts.

Pick the command that matches your system:

**Windows (PowerShell) — using `python`:**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**Windows (PowerShell) — using `py`:**
```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt) — using `python`:**
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

**Windows (Command Prompt) — using `py`:**
```cmd
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

> **✅ How to tell it worked:** Your terminal prompt should now start with `(.venv)`.
> Example: `(.venv) PS C:\Users\YourName\Smart Pick Pro>`

> **⚠️ PowerShell execution policy error?** If you see "running scripts is disabled on this system", run this first:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```
> Then try the activate command again.

> **📌 Every time you open a new terminal** to work on this project, you must activate the virtual environment again using the same activate command above.

---

### Step 5: Install Dependencies

With your virtual environment activated (you should see `(.venv)` in your prompt), run:

**Windows (PowerShell or CMD):**
```powershell
pip install -r requirements.txt
```

**macOS / Linux:**
```bash
pip install -r requirements.txt
```

> **💡 If `pip` is not found**, try one of these instead:
> ```bash
> python -m pip install -r requirements.txt
> python3 -m pip install -r requirements.txt
> py -m pip install -r requirements.txt
> ```

This will install all 22 packages needed by the app. It may take 2–5 minutes.

#### ❌ Common installation errors and fixes

<details>
<summary><strong>ERROR: "metadata-generation-failed" for pandas / numpy / catboost</strong></summary>

This means pip is trying to **build from source** because no pre-built wheel exists for your Python version.

**Fix:** You are on Python 3.14 (or another unsupported version). You MUST use Python 3.11 or 3.12.

Check your version:
```bash
python --version
```

If it says 3.14, go back to [Step 1](#step-1-install-python) and install Python 3.12. Then recreate the virtual environment:

```powershell
# Delete old venv and recreate with the right Python
# Windows:
rmdir /s /q .venv
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Mac/Linux:
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

</details>

<details>
<summary><strong>ERROR: "Could not find vswhere.exe" / Meson build error</strong></summary>

Same root cause as above — pip is trying to compile C code because there's no pre-built wheel for your Python version.

**Fix:** Switch to Python 3.11 or 3.12 (see steps above). You do NOT need to install Visual Studio Build Tools.

</details>

<details>
<summary><strong>ERROR: "pip: command not found" or "'pip' is not recognized"</strong></summary>

**Fix:** Use the module form of pip instead:
```bash
python -m pip install -r requirements.txt
# or
python3 -m pip install -r requirements.txt
# or (Windows)
py -m pip install -r requirements.txt
```

</details>

<details>
<summary><strong>ERROR: "Permission denied" on Mac/Linux</strong></summary>

**Do NOT use `sudo pip install`**. Instead, make sure you're in a virtual environment (see Step 4).

If you're in a venv and still getting permission errors:
```bash
pip install --user -r requirements.txt
```

</details>

<details>
<summary><strong>WARNING: "running scripts is disabled" in PowerShell</strong></summary>

Run this once and then retry:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

</details>

---

### Step 6: First-Run Setup (Bootstrap the Database)

Before launching the app for the first time, run the bootstrap script to pull NBA data and build the local database:

```bash
python bootstrap.py
```

> **💡** This script pulls the full 2025-26 season data and builds the prediction pipeline. It may take 10-20 minutes on the first run. Let it finish — don't close the terminal.

> **💡** If `python` doesn't work, use `python3` or `py` — whichever worked in Step 1.

---

### Step 7: Run the App

```bash
streamlit run Smart_Picks_Pro_Home.py
```

> **💡** If `streamlit` is not recognized, try:
> ```bash
> python -m streamlit run Smart_Picks_Pro_Home.py
> python3 -m streamlit run Smart_Picks_Pro_Home.py
> py -m streamlit run Smart_Picks_Pro_Home.py
> ```

Your browser will automatically open to **http://localhost:8501** with the app running! 🎉

---

### Step 8: Load Live Data

Once the app is running:

1. Go to the **⚙️ Settings** page (page 13) and enter your API keys (if you have them)
2. Go to **📡 Smart NBA Data** (page 9) and click **Smart Update** to fetch tonight's data
3. Go to **📡 Live Games** (page 1) and click **⚡ One-Click Setup** to load games + live props
4. Go to **⚡ Quantum Analysis Matrix** (page 3) and click **Run Analysis**

---

## 🔁 Daily Workflow (After Initial Setup)

Every time you want to use the app:

```bash
# 1. Open a terminal and navigate to the project folder
cd "path/to/Smart Pick Pro"

# 2. Activate the virtual environment
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Windows CMD:
.venv\Scripts\activate.bat
# Mac/Linux:
source .venv/bin/activate

# 3. Run the app
streamlit run Smart_Picks_Pro_Home.py
```

Then in the browser:
1. Click **📡 Live Games** → **⚡ One-Click Setup**
2. Click **⚡ Quantum Analysis Matrix** → **Run Analysis**
3. Review your picks!

---

## 🐳 Docker (Alternative Setup)

If you have Docker installed, you can skip all Python setup:

```bash
# Clone the repo and cd into it, then:
cp .env.example .env
# Edit .env with your API keys

docker compose up --build
```

The app will be available at **http://localhost:8501** and the API at **http://localhost:8000**.

---

## 📁 App Structure

```
Smart Pick Pro/
├── Smart_Picks_Pro_Home.py                              # Main entry point — home dashboard
├── bootstrap.py                        # First-run ETL bootstrap
├── webhook_server.py                   # Stripe webhook server
├── requirements.txt                    # All dependencies
├── README.md                           # This file
│
├── pages/
│   ├── 0_💦_Live_Sweat.py              # Live AI Panic Room — in-game tracking
│   ├── 1_📡_Live_Games.py             # Tonight's games + one-click setup
│   ├── 2_🔬_Prop_Scanner.py           # Enter/upload/fetch prop lines
│   ├── 3_⚡_Quantum_Analysis_Matrix.py # Run Neural Analysis — main engine
│   ├── 4_📋_Game_Report.py            # AI-powered game reports (SAFE Score™)
│   ├── 5_🔮_Player_Simulator.py       # What-if player scenario simulator
│   ├── 6_🧬_Entry_Builder.py          # Build optimal DFS entries (parlays)
│   ├── 7_🎙️_The_Studio.py            # Joseph M. Smith AI analyst desk
│   ├── 8_🛡️_Risk_Shield.py           # Flagged picks to avoid
│   ├── 9_📡_Smart_NBA_Data.py          # Smart NBA Data hub — stats, standings, leaders
│   ├── 10_🗺️_Correlation_Matrix.py   # Prop correlation analysis
│   ├── 11_📈_Bet_Tracker.py           # Bet tracking & model health
│   ├── 12_📊_Proving_Grounds.py         # Historical backtesting engine (Proving Grounds)
│   ├── 13_⚙️_Settings.py             # Configure engine settings
│   ├── 14_💎_Subscription_Level.py    # Premium subscription management
│   └── helpers/                        # Page helper modules
│       ├── bet_tracker_helpers.py
│       ├── joseph_live_desk.py
│       └── neural_analysis_helpers.py
│
├── engine/
│   ├── math_helpers.py                 # All math from scratch (no scipy)
│   ├── simulation.py                   # Quantum Matrix Engine 5.6 simulator
│   ├── projections.py                  # Player stat projections
│   ├── edge_detection.py              # Find betting edges + Goblin/Demon/Gold
│   ├── entry_optimizer.py             # Build optimal entries
│   ├── confidence.py                  # Confidence + tier system
│   ├── joseph_brain.py                # Joseph M. Smith AI persona engine
│   ├── arbitrage_matcher.py           # Cross-book EV scanner
│   ├── live_math.py                   # Live game pacing engine
│   ├── backtester.py                  # Historical backtesting engine
│   ├── calibration.py                 # Model calibration
│   ├── correlation.py                 # Prop correlation analysis
│   ├── ensemble.py                    # Multi-model ensemble combiner
│   ├── game_prediction.py             # Full game outcome prediction
│   ├── game_script.py                 # Game script / flow analysis
│   ├── impact_metrics.py              # Player impact metrics
│   ├── lineup_analysis.py             # Lineup analysis engine
│   ├── minutes_model.py               # Minutes projection model
│   ├── player_intelligence.py         # Deep player intelligence
│   ├── regime_detection.py            # Play-style regime detection
│   ├── stat_distributions.py          # Statistical distribution models
│   ├── features/                      # Feature engineering
│   │   ├── feature_engineering.py
│   │   ├── player_metrics.py
│   │   └── team_metrics.py
│   ├── models/                        # ML models (XGBoost, CatBoost, Ridge)
│   │   ├── base_model.py
│   │   ├── catboost_model.py
│   │   ├── ensemble.py
│   │   ├── ridge_model.py
│   │   ├── train.py
│   │   └── xgboost_model.py
│   ├── pipeline/                      # ML pipeline (ingest → export)
│   │   ├── run_pipeline.py
│   │   ├── step_1_ingest.py
│   │   ├── step_2_clean.py
│   │   ├── step_3_features.py
│   │   ├── step_4_predict.py
│   │   ├── step_5_evaluate.py
│   │   └── step_6_export.py
│   ├── predict/                       # Prediction engine
│   │   └── predictor.py
│   └── scrapers/                      # External data scrapers
│       ├── basketball_ref_scraper.py
│       ├── cbs_injuries_scraper.py
│       └── transactions_scraper.py
│
├── data/
│   ├── data_manager.py                # Load/save CSV data + session state
│   ├── db_service.py                  # Local SQLite DB gateway for engine
│   ├── etl_data_service.py            # ETL data service (reads smartpicks.db)
│   ├── nba_data_service.py            # NBA data orchestration service
│   ├── nba_live_fetcher.py            # Live NBA.com data fetcher
│   ├── live_data_fetcher.py           # Live data fetching + enrichment
│   ├── sportsbook_service.py          # Multi-platform prop fetcher
│   ├── platform_fetcher.py            # Async platform line fetcher
│   ├── live_game_tracker.py           # Live game score tracker
│   ├── player_profile_service.py      # Player context & headshots
│   ├── player_id_cache.py             # Player ID resolution cache
│   ├── roster_engine.py               # Active roster & injury engine
│   ├── advanced_fetcher.py            # Advanced stats fetcher
│   ├── advanced_metrics.py            # Advanced metric calculations
│   ├── validators.py                  # Data validation utilities
│   ├── nba_injury_pdf/                # NBA injury report PDF parser
│   ├── teams.csv                      # All 30 NBA teams with pace/ratings
│   └── defensive_ratings.csv          # Team defense by position
│
├── etl/                                # ETL pipeline (writes to smartpicks.db)
│   ├── setup_db.py                    # Database schema setup (39 tables)
│   ├── initial_pull.py                # Full historical data pull
│   ├── data_updater.py                # Incremental data updates
│   ├── api.py                         # ETL FastAPI endpoints
│   └── utils.py                       # ETL utility functions
│
├── api/                                # REST API (FastAPI)
│   ├── main.py                        # API app entry point
│   ├── middleware.py                   # API middleware
│   └── routes/                        # API route handlers
│       ├── health.py
│       ├── players.py
│       └── predictions.py
│
├── agent/
│   ├── payload_builder.py             # Live Sweat game state classifier
│   ├── live_persona.py                # Joseph's live commentary persona
│   └── response_parser.py             # Vibe response parsing
│
├── config/
│   └── thresholds.py                  # Configurable thresholds
│
├── styles/
│   ├── theme.py                       # Global CSS + education box helpers
│   └── live_theme.py                  # Live Sweat custom CSS
│
├── utils/
│   ├── components.py                  # Shared UI components
│   ├── joseph_widget.py               # Joseph floating widget
│   ├── premium_gate.py                # Premium feature gates
│   ├── stripe_manager.py              # Stripe subscription management
│   ├── auth.py                        # Authentication utilities
│   ├── cache.py                       # Caching utilities
│   ├── logger.py                      # Logging configuration
│   ├── renderers.py                   # UI renderers
│   ├── rate_limiter.py                # API rate limiting
│   ├── parquet_helpers.py             # Parquet file helpers
│   └── ...                            # + constants, headers, geo, etc.
│
├── tracking/
│   ├── bet_tracker.py                 # Log bets + results
│   ├── database.py                    # SQLite wrapper
│   └── model_performance.py           # Model performance tracking
│
├── scripts/                            # Utility scripts
│
└── db/
    └── smartpicks.db                   # ETL database (created by etl/setup_db.py)
```

---

## 📖 What Each Page Does

### 🏠 Home (Smart_Picks_Pro_Home.py)
The dashboard. Shows tonight's slate, quick-start workflow guide, status
dashboard, and links to all pages.

### 💦 Page 0: Live Sweat
The Live AI Panic Room — track your active bets in real-time during games.
Features pace tracking, Joseph M. Smith live commentary, and sweat cards
that show whether your bets are on track to cash.

### 📡 Page 1: Live Games
Load tonight's matchups, fetch rosters and stats from API-NBA API,
and enrich with Odds API consensus lines. Features:
- **⚡ One-Click Setup** — loads games + fetches live platform props in one step
- **Auto-Load** — fetches tonight's schedule, rosters, player/team stats
- **Fetch Platform Props** — pulls real live lines from PrizePicks, Underdog, DraftKings

### 🔬 Page 2: Prop Scanner
Enter prop lines manually, upload a CSV, or fetch live lines from platforms.
Three input methods:
- Manual form entry
- CSV upload
- Live platform fetch (from the Live Games page)

### ⚡ Page 3: Neural Analysis (Quantum Analysis Matrix)
The main engine. Click **Run Analysis** to simulate each prop. For every prop you'll see:
- **Probability**: % chance of going over (or under) the line
- **Edge**: How far above 50% the probability is (bigger = better)
- **Tier**: Platinum 💎, Gold 🥇, Silver 🥈, or Bronze 🥉
- **Direction**: OVER or UNDER
- **Forces**: All the factors pushing the stat up or down
- **Win Score**: Composite score combining probability, confidence, edge, and risk
- **Fair-Value Odds Explorer**: Slide to see fair odds at different prop lines

### 📋 Page 4: Game Report
AI-powered game reports with SAFE Score™ analysis, collapsible sections,
confidence bars, and entry strategy matrix.

### 🔮 Page 5b: Player Simulator
What-if scenario simulator. Adjust minutes, pace, matchup factors and see
how projected stats change in real-time.

### 🧬 Page 6: Entry Builder
Build optimal DFS parlays. The engine tests all combinations of top picks
and finds the ones with the highest **Expected Value (EV)**. Supports
PrizePicks, Underdog, and DraftKings payout structures.

### 🎙️ Page 7: The Studio
Joseph M. Smith's broadcast desk. Three modes:
- **Games Tonight** — Joseph breaks down every game
- **Scout a Player** — deep-dive player analysis
- **Build My Bets** — Joseph constructs optimal tickets

### 🛡️ Page 8: Risk Shield
Shows which props to skip and explains exactly WHY:
- Low edge, trap lines, sharp lines, high variance, low confidence
- Educational content explains each risk flag

### 📡 Page 9: Smart NBA Data
Your complete NBA data hub — pull stats, browse league leaders, view standings & playoff picture:
- **Player Stats** — browse season averages for all loaded players
- **Stat Leaders** — top performers in scoring, rebounds, assists, steals, blocks, 3PM
- **Team Stats** — team metrics including pace, ORTG, DRTG, and net rating
- **Standings** — conference standings with W-L records and streaks
- **Playoff Picture** — seedings, play-in positions, and lottery bound teams
- **Smart Update** — only tonight's teams (fast)
- **Full Update** — all NBA player stats
- **Fetch Props** — live odds from sportsbooks

### 🗺️ Page 10: Correlation Matrix
Analyze how player props correlate with each other within games.
Helps build smarter parlays by avoiding correlated risk.

### 📈 Page 11: Bet Tracker & Model Health
Track your betting results. Features:
- Overall win rate by tier
- Auto-resolve bets against real game results
- Model health monitoring
- Performance predictor and bankroll allocation

### 📊 Page 12: Backtester
Validate the model against historical game logs. See win rates, ROI,
and tier-by-tier performance metrics.

### ⚙️ Page 13: Settings
Configure:
- **Simulation Depth**: 500 (fast) to 5,000 (most accurate)
- **Minimum Edge**: How much edge before showing a pick (default: 5%)
- **Preset Profiles**: Conservative, Balanced, Aggressive, Research
- **API Keys**: Odds API + API-NBA API keys
- **Advanced factors**: Home court boost, fatigue sensitivity, etc.

### 💎 Page 14: Subscription Level
Premium subscription management powered by Stripe.

---

## 🔴 Live NBA Data

Smart Pick Pro uses **real, up-to-date NBA stats** from the **nba_api** Python package and
prop lines from **PrizePicks**, **Underdog Fantasy**, and **DraftKings Pick6**.

### Setup

1. Install all dependencies (see [Quick Start](#-quick-start-complete-beginner-guide) above)
2. Run `python bootstrap.py` to build the local database
3. Run `streamlit run Smart_Picks_Pro_Home.py`
4. Optionally configure API keys:
   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   # Edit .streamlit/secrets.toml and replace the placeholder values with your real keys
   ```
5. Go to **📡 Smart NBA Data** (page 9) and click **Smart Update** to fetch tonight's data
6. Go to **📡 Live Games** (page 1) and click **⚡ One-Click Setup** to load games + live props

### When to Update

- **Before each betting session** for best accuracy
- Player and team situations change throughout the season
- The home page shows when data was last updated

### What Gets Updated

| Data | Source | Storage |
|------|--------|---------|
| Player stats (PPG, RPG, APG, etc.) | nba_api + API-NBA API | `db/smartpicks.db` |
| Team pace + ratings (ORTG/DRTG) | nba_api + API-NBA API | `db/smartpicks.db` |
| Player game logs | nba_api | `db/smartpicks.db` |
| Tonight's games + spreads/totals | API-NBA API + Odds API | Session state |
| Live prop lines | The Odds API (15+ books) | Session state |
| Defensive ratings by position | Calculated from team DRTG | `data/defensive_ratings.csv` |

---

## 📊 How to Add Your Own Data

### Adding a New Player
Go to **📡 Smart NBA Data** and run a **Smart Update** to pull tonight's active roster.
Player data is stored in `data/players.csv` — you can also edit it directly.

### Entering Tonight's Props
Go to **🔬 Prop Scanner** (page 2) and either:
1. Type them in the form (one at a time)
2. Upload a CSV using the template provided
3. Or use **📡 Live Games** → **📊 Fetch Platform Props** to pull real live lines automatically

---

## 🔧 Troubleshooting

### Python command not found / wrong version

The Python command varies by operating system and installation method. Try **all** of these:

```bash
python --version       # Most common on Windows
python3 --version      # Most common on Mac/Linux
py --version           # Windows Python Launcher
py -3.12 --version     # Specific version on Windows
```

Use whichever one shows a version between 3.11 and 3.13.

### `pip install` fails with "metadata-generation-failed" or "Meson build error"

**Cause:** You're using Python 3.14 (or another version without pre-built wheels).

**Fix:** Install Python 3.11 or 3.12 and recreate your virtual environment. See [Step 1](#step-1-install-python).

### "streamlit: command not found" / "'streamlit' is not recognized"

**Fix A** — Make sure you're in your virtual environment (you should see `(.venv)` in your prompt).

**Fix B** — Use the module form:
```bash
python -m streamlit run Smart_Picks_Pro_Home.py
```

### "ModuleNotFoundError: No module named '...'"

**Fix:** Run `pip install -r requirements.txt` inside your activated virtual environment.

If you're not sure which pip goes with which Python:
```bash
python -m pip install -r requirements.txt
```

### "Port 8501 is already in use"

Another Streamlit app is running. Close it, or run on a different port:
```bash
streamlit run Smart_Picks_Pro_Home.py --server.port 8502
```

### "running scripts is disabled on this system" (PowerShell)

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then retry the activate command.

### Live data update takes too long

This is normal! The fetcher adds a 1.5-second delay between API calls to avoid
being blocked by the NBA's servers. A full update (all players + game logs) can
take 5–15 minutes. Let it run — don't close the tab.

### App shows "No props loaded"

Go to **🔬 Prop Scanner** (page 2) and either enter props manually, upload a CSV, or use **📡 Live Games** → **⚡ One-Click Setup** to fetch live lines.

### Analysis results seem off

Check that you have:
1. Games configured on **📡 Live Games** (page 1) — use **⚡ One-Click Setup**
2. Run a **Smart Update** on the **📡 Smart NBA Data** page to load live player data
3. Stat types are lowercase: `points`, `rebounds`, `assists`, `threes`, etc.

---

## 🧠 How the Math Works (Plain English)

### Quantum Matrix Engine 5.6 Simulation
We simulate 1,000 games for each player. In each game:
1. **Minutes** are randomized (sometimes stars rest, sometimes foul trouble)
2. **Stats** are drawn randomly from a bell curve centered on the projection
3. We record whether that game went OVER or UNDER the line

After 1,000 games: `(# games over line) / 1000 = probability of going over`

### Normal Distribution (Bell Curve)
Player stats follow a bell curve — most games near the average, fewer extreme games.
We use the formula `0.5 * (1 + erf(z / √2))` to calculate probabilities.
This is exactly what scipy.stats.norm.cdf does — we just wrote it ourselves!

### Expected Value (EV)
For a parlay with 3 picks:
```
EV = (P(all 3 hit) × 3-pick payout) + (P(2 hit) × 2-hit payout) + ... - entry fee
```
Positive EV = profitable on average. Negative EV = house wins.

---

## 📦 Dependencies

### Core
| Package | Purpose |
|---------|---------|
| `streamlit` | UI framework |
| `streamlit-autorefresh` | Auto-refresh for live pages |
| `pandas` | Data manipulation & analysis |
| `numpy` | Numerical computing |
| `requests` | HTTP client for API calls |
| `aiohttp` | Async HTTP for platform fetching |

### Machine Learning
| Package | Purpose |
|---------|---------|
| `scikit-learn` | Ridge regression model |
| `xgboost` | Gradient boosted tree model |
| `catboost` | CatBoost ensemble model |
| `joblib` | Model serialization |

### Data & Parsing
| Package | Purpose |
|---------|---------|
| `nba_api` | NBA.com stats API client |
| `beautifulsoup4` | HTML parsing for scrapers |
| `lxml` | Fast XML/HTML parser backend |
| `pdfplumber` | NBA injury report PDF parsing |
| `pyarrow` | Parquet file I/O engine |
| `thefuzz` | Fuzzy string matching for player names |

### API & Web
| Package | Purpose |
|---------|---------|
| `fastapi` | REST API framework |
| `uvicorn` | ASGI server for FastAPI |
| `flask` | Stripe webhook server |
| `stripe` | Payment processing |
| `python-dotenv` | Environment variable management |

Install all:
```bash
pip install -r requirements.txt
```

The engine also uses Python's standard library extensively:
`math`, `random`, `statistics`, `csv`, `sqlite3`, `datetime`, `os`, `pathlib`,
`itertools`, `collections`, `json`, `io`, `copy`

---

## 🚀 Production Deployment

### Streamlit Community Cloud

1. **Push to GitHub** — fork or push this repo to your GitHub account.
2. **Connect to Streamlit Cloud** — go to [share.streamlit.io](https://share.streamlit.io) and create a new app from your repo.
3. **Set secrets** — in the Streamlit Cloud dashboard, go to **Settings → Secrets** and paste your secrets (see `.streamlit/secrets.toml.example` for the full list). Do **not** commit `secrets.toml` to Git.
4. **Set `SMARTAI_PRODUCTION=true`** — this enforces Stripe subscription gates.
5. **Set `APP_URL`** — your deployed app URL (e.g., `https://your-app.streamlit.app`).

### Docker Deployment

```bash
cp .env.example .env
# Edit .env with your real API keys and Stripe keys

docker compose up --build -d
```

This starts the Streamlit UI (port 8501), the FastAPI backend (port 8000), and Caddy reverse proxy (ports 80/443).

### Environment Variables Checklist

| Variable | Required | Description |
|----------|----------|-------------|
| `ODDS_API_KEY` | For DraftKings | The Odds API key (powers DraftKings Pick6 props) |
| `STRIPE_SECRET_KEY` | For payments | Stripe secret key |
| `STRIPE_PUBLISHABLE_KEY` | For payments | Stripe publishable key |
| `STRIPE_PRICE_ID` | For payments | Stripe product price ID |
| `STRIPE_WEBHOOK_SECRET` | Recommended | Stripe webhook signing secret |
| `SMARTAI_PRODUCTION` | For production | Must be `"true"` to enforce gates |
| `APP_URL` | For Stripe redirects | Your deployed app URL |
| `DB_PATH` | Optional | Override default SQLite path |
| `LOG_LEVEL` | Optional | DEBUG, INFO, WARNING, ERROR |

### Stripe Webhook Setup

1. Deploy `webhook_server.py` to a hosting platform (Railway, Render, or Fly.io).
2. In the Stripe Dashboard → Developers → Webhooks, register your webhook URL (e.g., `https://your-server.railway.app/webhook`).
3. Select events: `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`.
4. Copy the signing secret (`whsec_...`) and add it as `STRIPE_WEBHOOK_SECRET` to both the webhook server and the Streamlit app.

### Pre-Launch Checklist

- [ ] All environment variables set (see table above)
- [ ] `SMARTAI_PRODUCTION=true` confirmed
- [ ] Stripe keys are live keys (not test keys)
- [ ] API-NBA and Odds API keys are active with sufficient credits
- [ ] Run `scripts/verify_api_endpoints.py` to confirm API connectivity
- [ ] Run `python -m pytest tests/` to confirm all tests pass
- [ ] SQLite database initialized (first run auto-creates it)
- [ ] Stripe webhook endpoint registered and tested with Stripe CLI

---

## 🧪 Running Tests

```bash
# Make sure you're in the virtual environment first
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```

---

## ⚠️ Disclaimer

This app is for **personal entertainment and analysis** only.
Always gamble responsibly. Past model performance does not guarantee future results.
Prop betting involves risk. Never bet more than you can afford to lose.

**Responsible Gambling:** If you or someone you know has a gambling problem, call
the National Council on Problem Gambling helpline at **1-800-522-4700** or visit
[www.ncpgambling.org](https://www.ncpgambling.org).
