# F1 Strategy Dashboard

A self-hosted Formula 1 strategy dashboard built for race weekends. Pulls live timing data directly from F1's official feed during sessions, and falls back to FastF1 for historical data when the live ingestor isn't running. Runs on a Debian VM and is accessible across your LAN from any device.

Forked from [bordanattila/OpenF1_tutorial](https://github.com/bordanattila/OpenF1_tutorial) — significantly extended.

---

## 📊 Features

- **11 interactive charts** across tabs — lap times, sector times, tyre strategy, pit stops, race position, head-to-head comparison, tyre degradation, weather, race control messages, track map, and session results
- **Championship pages** — driver and constructor standings with points progression and a round-by-round championship position tracker
- **Schedule & Results** — full season calendar with session results per race
- **Smart defaults** — automatically selects the current or most recent race weekend and session on load
- **Driver filter** — sidebar shows colour-coded driver roster cards; multiselect to focus on specific drivers across all charts
- **Session-aware** — charts that don't apply to a session type show an explanatory message rather than an error
- **Live mode** — auto-detects active sessions and refreshes charts every 30 seconds with a pulsing LIVE badge
- **Dual data source** — live sessions use a local OpenF1 ingestor writing to MongoDB; historical sessions fall back to FastF1 automatically
- **F1TV token management** — dashboard Token page with bookmarklet for one-click token refresh; validates JWT expiry and restarts the ingestor automatically
- **F1 dark theme** — Titillium Web font, branded colour scheme, unified Plotly dark theme across all charts
- **LAN accessible** — runs on `0.0.0.0:8501`, accessible from tablets, laptops, and widescreen monitors on the same network

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│           Streamlit App :8501           │
│                                         │
│  main.py → app/charts/ (11 modules)     │
│         → app/pages/ (schedule,         │
│                        standings)       │
│         → app/data_loader.py            │
│         → app/fastf1_fallback.py        │
│         → app/jolpica.py               │
└──────────────┬──────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
       ▼                ▼
Local API :8008      FastF1 library
(br-g/openf1)        (historical fallback)
       │
       ▼
   MongoDB
       │
       ▼
OpenF1 ingestor
(F1 live timing feed)
```

### Data flow

- **During a live session** — the OpenF1 ingestor connects to `livetiming.formula1.com`, processes the timing stream, and writes to MongoDB. The Streamlit app queries the local REST API (port 8008) which reads from MongoDB.
- **Historical sessions** — the local MongoDB has no data, so `data_loader.py` raises `OpenF1Unavailable` and the app transparently falls back to FastF1, which loads from F1's official cached timing data.
- **Championship / schedule data** — fetched from the [Jolpica API](https://api.jolpi.ca) (Ergast successor), cached for 5 minutes.

---

## 🗂️ Project Structure

```
OpenF1/
├── app/
│   ├── charts/
│   │   ├── base.py              # F1Chart base class, Plotly f1_dark template, shared config
│   │   ├── __init__.py          # Chart registry — add new charts here
│   │   ├── lap_times.py
│   │   ├── sector_times.py
│   │   ├── tire_strategy.py
│   │   ├── pit_stops.py
│   │   ├── position_tracker.py  # Race/Sprint only
│   │   ├── head_to_head.py
│   │   ├── tyre_degradation.py
│   │   ├── weather.py
│   │   ├── race_control.py
│   │   ├── track_map.py
│   │   └── results.py
│   ├── pages/
│   │   ├── schedule.py          # Schedule & Results page
│   │   └── standings.py         # Championship standings + position tracker
│   ├── data_loader.py           # Local OpenF1 API client
│   ├── data_processor.py        # Data cleaning and colour mapping
│   ├── fastf1_fallback.py       # FastF1 fallback data source
│   └── jolpica.py               # Jolpica/Ergast API client (standings, schedule)
├── .streamlit/
│   └── config.toml              # LAN server config + F1 dark theme
├── main.py                      # Streamlit app — session selection, tabs, sidebar
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env                         # Local config — not committed
```

---

## 🛠️ Setup

### Prerequisites

- Debian/Ubuntu VM (tested on Debian 12)
- Python 3.10+
- Docker (for MongoDB)
- 10GB+ free disk space (FastF1 cache grows over a season)

### 1. Clone the repo

```bash
git clone https://github.com/mattellingham/OpenF1.git
cd OpenF1
```

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure `.env`

```bash
nano .env
```

```
BASE_API_URL=http://localhost:8008/v1/
```

### 4. Start MongoDB

```bash
mkdir -p ~/mongodb-data
docker run -d \
  --name openf1-mongo \
  --restart unless-stopped \
  -p 27017:27017 \
  -v ~/mongodb-data:/data/db \
  mongo:7
```

### 5. Set up the OpenF1 ingestor

```bash
cd ~
git clone https://github.com/br-g/openf1.git
cd openf1
python3 -m venv venv-openf1
source venv-openf1/bin/activate
pip install -e .
sudo ln -sf /usr/bin/python3 /usr/bin/python  # Debian only — -f avoids "File exists" error
pip install fastf1-livetiming  # required by the ingestor recorder subprocess
```

Create `~/openf1/.env-openf1`:
```
MONGO_CONNECTION_STRING=mongodb://localhost:27017
F1_TOKEN=your_f1tv_entitlement_token_here
```

> **F1TV token:** The initial token can be obtained by logging in to [f1tv.formula1.com](https://f1tv.formula1.com) in Firefox/Chrome, opening DevTools → Application → Cookies, and copying the value of `entitlement_token`. Paste it into `.env-openf1`. After setup, use the dashboard's **🔑 Token** page and bookmarklet to refresh it — tokens expire every 4 days.

### 6. Install systemd services

**`/etc/systemd/system/openf1-api.service`**
```ini
[Unit]
Description=OpenF1 Local Query API
After=network.target docker.service

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/openf1
EnvironmentFile=/home/your_username/openf1/.env-openf1
ExecStart=/home/your_username/openf1/venv-openf1/bin/uvicorn openf1.services.query_api.app:app --host 0.0.0.0 --port 8008
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/openf1-ingestor.service`**
```ini
[Unit]
Description=OpenF1 Live Timing Ingestor
After=network.target docker.service openf1-api.service

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/openf1
EnvironmentFile=/home/your_username/openf1/.env-openf1
ExecStart=/home/your_username/openf1/venv-openf1/bin/python -m openf1.services.ingestor_livetiming.real_time.app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/openf1.service`** (Streamlit app)
```ini
[Unit]
Description=OpenF1 Streamlit Dashboard
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/OpenF1
ExecStart=/home/your_username/OpenF1/venv/bin/streamlit run main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable openf1 openf1-api openf1-ingestor
sudo systemctl start openf1 openf1-api openf1-ingestor
```

### 7. Open firewall port

```bash
sudo ufw allow 8501/tcp
```

---

## 🚀 Usage

Access the dashboard at `http://<your-vm-ip>:8501` from any device on your LAN.

Select year → country → session. The app defaults to the current race weekend and the most recently started session. The sidebar shows a colour-coded driver roster — use the multiselect below it to filter to specific drivers. All 11 charts update automatically based on your selection.

### Pages

| Page | Description |
|---|---|
| **📊 Session Analysis** | Main view — all 11 chart tabs for the selected session |
| **📅 Schedule & Results** | Full season calendar with session-by-session results |
| **🏆 Championship** | Driver and constructor standings, points progression, and position tracker |
| **🔑 Token** | F1TV token status and one-click refresh via bookmarklet |

### Live sessions

The ingestor needs to be running **before** a session starts:
- Practice / Qualifying: at least **15 minutes** before
- Race: at least **1 hour** before

The ingestor runs permanently as a systemd service so this is handled automatically. Check it's healthy before a race weekend:

```bash
sudo systemctl status openf1-ingestor
journalctl -u openf1-ingestor -f
```

### F1TV token refresh

Tokens expire every 4 days. Refresh via the dashboard:

1. Log in to [f1tv.formula1.com](https://f1tv.formula1.com) in your browser
2. Click the **F1TV Token** bookmarklet (setup instructions in the dashboard under **🔑 Token**)
3. Paste the copied token into the Token page and click **Update Token**

The dashboard validates the token, updates `.env-openf1`, and restarts the ingestor automatically. The Token page shows the current expiry so you know when a refresh is due.

> **Sudoers requirement:** The dashboard restarts the ingestor via `sudo systemctl`. Add the following to allow this without a password prompt:
> ```bash
> echo 'your_username ALL=(ALL) NOPASSWD: /bin/systemctl restart openf1-ingestor' | sudo tee /etc/sudoers.d/openf1-ingestor
> sudo chmod 440 /etc/sudoers.d/openf1-ingestor
> ```

---

## ➕ Adding a new chart

1. Create `app/charts/my_chart.py` inheriting from `F1Chart`
2. Set `tab_label`, `session_types`, and `unavailable_message`
3. Implement `render(context)`
4. Add to `REGISTRY` in `app/charts/__init__.py`

```python
from app.charts.base import F1Chart, ALL_SESSIONS

class MyChart(F1Chart):
    tab_label = "🔧 My Chart"
    session_types = ALL_SESSIONS
    unavailable_message = "Not available for this session type."

    def render(self, context: dict) -> None:
        import streamlit as st
        st.write("Hello from my chart!")
        # context keys: session_key, session_type, country, year,
        #               driver_info, color_map, selected_drivers,
        #               fastf1_mode, is_live
```

The global `f1_dark` Plotly template in `base.py` is applied automatically to every `go.Figure()` — no per-chart theming needed.

---

## 🔧 Useful commands

```bash
# Check all services
sudo systemctl status openf1 openf1-api openf1-ingestor

# Live ingestor logs
journalctl -u openf1-ingestor -f

# Streamlit app logs
journalctl -u openf1 -f

# Test local API
curl "http://localhost:8008/v1/sessions?year=2026"

# FastF1 cache size
du -sh ~/.fastf1_cache
```

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `streamlit` | Web UI framework |
| `fastf1` | Historical F1 data fallback |
| `plotly` | Interactive charts |
| `pandas` | Data processing |
| `requests` | Local API client + Jolpica API |
| `numpy` | Tyre degradation trend lines |
| `python-dotenv` | `.env` file loading |

External APIs (no package required):
- **[Jolpica](https://api.jolpi.ca)** — championship standings, race results, season schedule

---

## 🗺️ Roadmap

- [x] Default to current race weekend on load (#20)
- [x] F1TV token refresh — bookmarklet + dashboard Token page (#24)
- [x] Sector time breakdown chart (#25)
- [x] Driver standings tracker across the season (#26)
- [x] UI/UX refresh — F1 dark theme, session header, driver roster cards, pulsing live badge (#27)
- [ ] Historical backfill via the `br-g/openf1` historical ingestor (2023–2025 data in local MongoDB) (#23)
