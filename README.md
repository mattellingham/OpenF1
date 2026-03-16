# F1 Strategy Dashboard

A self-hosted Formula 1 strategy dashboard built for race weekends. Pulls live timing data directly from F1's official feed during sessions, and falls back to FastF1 for historical data when the live ingestor isn't running. Runs on a Debian VM and is accessible across your LAN from any device.

Forked from [bordanattila/OpenF1_tutorial](https://github.com/bordanattila/OpenF1_tutorial) — significantly extended.

---

## 📸 Screenshots

> **Replace these placeholders with your own screenshots**

| Chart | Screenshot |
|---|---|
| Lap Times | `assets/screenshot_lap_times.png` |
| Tire Strategy | `assets/screenshot_tire_strategy.png` |
| Pit Stops | `assets/screenshot_pit_stops.png` |
| Race Position | `assets/screenshot_race_position.png` |
| Head to Head | `assets/screenshot_head_to_head.png` |
| Tyre Degradation | `assets/screenshot_tyre_deg.png` |
| Weather | `assets/screenshot_weather.png` |
| Race Control | `assets/screenshot_race_control.png` |

---

## 📊 Features

- **8 interactive charts** across tabs — lap times, tire strategy, pit stops, race position, head-to-head comparison, tyre degradation, weather, and race control messages
- **Driver filter** — sidebar multiselect to focus on specific drivers across all charts
- **Session-aware** — charts that don't apply to a session type (e.g. race position in qualifying) show an explanatory message rather than an error
- **Live mode** — auto-detects active sessions and refreshes charts every 30 seconds with a 🔴 LIVE badge
- **Dual data source** — live sessions use a local OpenF1 ingestor writing to MongoDB; historical sessions use FastF1 as a fallback
- **Resilient** — if the local API has no data, the app falls back to FastF1 automatically with no manual intervention
- **LAN accessible** — runs on `0.0.0.0:8501`, accessible from tablets, laptops, and widescreen monitors on the same network

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│           Streamlit App :8501           │
│                                         │
│  main.py → app/charts/ (8 modules)      │
│         → app/data_loader.py            │
│         → app/fastf1_fallback.py        │
└──────────────┬──────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
       ▼                ▼
Local API :8000      FastF1 library
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

- **During a live session** — the OpenF1 ingestor connects to `livetiming.formula1.com`, processes the timing stream, and writes to MongoDB. The Streamlit app queries the local REST API (port 8000) which reads from MongoDB.
- **Historical sessions** — the local MongoDB has no data, so `data_loader.py` raises `OpenF1Unavailable` and the app transparently falls back to FastF1, which loads from F1's official cached timing data.

---

## 🗂️ Project Structure

```
OpenF1/
├── app/
│   ├── charts/
│   │   ├── base.py              # F1Chart base class and shared config
│   │   ├── __init__.py          # Chart registry — add new charts here
│   │   ├── lap_times.py
│   │   ├── tire_strategy.py
│   │   ├── pit_stops.py
│   │   ├── position_tracker.py  # Race/Sprint only
│   │   ├── head_to_head.py
│   │   ├── tyre_degradation.py
│   │   ├── weather.py
│   │   └── race_control.py
│   ├── data_loader.py           # Local OpenF1 API client
│   ├── data_processor.py        # Data cleaning and colour mapping
│   └── fastf1_fallback.py       # FastF1 fallback data source
├── .streamlit/
│   └── config.toml              # Binds to 0.0.0.0:8501 for LAN access
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
BASE_API_URL=http://localhost:8000/v1/
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
sudo ln -s /usr/bin/python3 /usr/bin/python  # Debian only
```

Create `~/openf1/.env-openf1`:
```
MONGO_CONNECTION_STRING=mongodb://localhost:27017
F1_TOKEN=your_f1tv_entitlement_token_here
```

> **Getting your F1TV token:** Log in to F1TV in Firefox with the Network tab open. Find the POST request to `api.formula1.com`. Look in Storage → Cookies or Local Storage for `entitlement_token`. Tokens expire every 4 days — update `.env-openf1` and restart `openf1-ingestor` when it does.

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
ExecStart=/home/your_username/openf1/venv-openf1/bin/uvicorn openf1.services.query_api.app:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/openf1-ingestor.service`**
```ini
[Unit]
Description=OpenF1 Live Timing Ingestor
After=network.target docker.service

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

Select year → country → session. The sidebar lets you filter to specific drivers. All 8 charts update automatically based on your selection.

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

Tokens expire every 4 days. When one expires:

```bash
nano ~/openf1/.env-openf1   # Update F1_TOKEN
sudo systemctl restart openf1-ingestor
```

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
curl "http://localhost:8000/v1/sessions?year=2026"

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
| `requests` | Local API client |
| `numpy` | Tyre degradation trend lines |
| `python-dotenv` | `.env` file loading |

---

## 🗺️ Roadmap

- [ ] Historical backfill via the `br-g/openf1` historical ingestor (2023–2025 data in local MongoDB)
- [ ] Automated F1TV token refresh
- [ ] Sector time breakdown chart
- [ ] Driver standings tracker across the season
