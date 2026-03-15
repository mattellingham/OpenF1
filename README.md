# OpenF1 API: Interactive F1 Strategy Dashboard

An interactive Formula 1 strategy dashboard built with the OpenF1 API, Streamlit, and Plotly. Supports historical data browsing (2023–2026) and live session auto-refresh during active race weekends.

Forked from [bordanattila/OpenF1_tutorial](https://github.com/bordanattila/OpenF1_tutorial).

## 📊 Features

- Select race sessions by year (2023–2026) and country
- View lap times per driver with pit-out lap flags
- Analyse tire strategy over the race distance
- Compare pit stop durations
- 🔴 **Live mode** — auto-detects active sessions and refreshes charts every 30 seconds
- Authenticated access to real-time and 2026 data via OpenF1 OAuth2

## 📸 Screenshots

![lap_time_chart](./assets/Screenshot1.png)
![tyre_strategy_chart](./assets/Screenshot2.png)
![pit_stop_chart](./assets/Screenshot3.png)

## 🗂 Project Structure

```
OpenF1/
├── app/
│   ├── data_loader.py        # OpenF1 API requests, auth, and caching
│   ├── data_processor.py     # Cleans and enriches raw API data
│   └── visualizer.py         # Builds Plotly charts
├── .streamlit/
│   └── config.toml           # Binds to 0.0.0.0:8501 for LAN access
├── main.py                   # Streamlit app logic and live/historical routing
├── requirements.txt          # Pinned Python dependencies
├── Dockerfile                # Container build
├── docker-compose.yml        # One-command container deployment
└── .env                      # Credentials and API base URL (not committed)
```

## 🛠️ Setup

### 1. Clone the repo

```bash
git clone https://github.com/mattellingham/OpenF1.git
cd OpenF1
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure `.env`

```bash
cp .env.example .env
nano .env
```

Fill in your values:

```
BASE_API_URL=https://api.openf1.org/v1/

# Required for 2026 data and live sessions
# Get access at: https://openf1.org/auth.html
OPENF1_USERNAME=your_username_or_email
OPENF1_PASSWORD=your_password
```

If you leave the credentials blank the app will still work for historical data (2023–2025) without authentication.

## 🚀 Running the App

### Directly

```bash
streamlit run main.py
```

Access at `http://localhost:8501`, or `http://<your-ip>:8501` from other devices on your LAN.

### As a persistent background service (Linux/systemd)

```bash
sudo nano /etc/systemd/system/openf1.service
```

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

```bash
sudo systemctl daemon-reload
sudo systemctl enable openf1
sudo systemctl start openf1
```

Check status: `sudo systemctl status openf1`
View logs: `journalctl -u openf1 -f`

### With Docker

```bash
docker compose up -d
```

Access at `http://<your-ip>:8501`.

## 🔑 Authentication

Access to 2026 data and real-time sessions requires a paid OpenF1 account. You can get access at [openf1.org/auth.html](https://openf1.org/auth.html).

Once configured in `.env`, the app handles OAuth2 token management automatically — tokens are fetched on first request, cached in memory, and refreshed before expiry. No manual token handling needed.

## 🔴 Live Mode

When a session is currently in progress, the app automatically switches to live mode:

- A **🔴 LIVE** badge appears in the session header
- All three charts refresh independently every 30 seconds using Streamlit fragments
- Live data fetchers use a 30-second cache TTL; historical fetchers cache indefinitely

The refresh interval can be tuned by changing `LIVE_REFRESH_SECONDS` at the top of `main.py`.

## 🔍 File Descriptions

**`app/data_loader.py`** handles all OpenF1 API communication. It manages OAuth2 token acquisition and caching, attaches `Authorization` headers when credentials are present, and returns empty DataFrames for 404 (session not yet available) and 502/503 (API outage) responses rather than crashing. Each endpoint has both a permanent-cache and a 30-second TTL variant for live use.

**`app/data_processor.py`** cleans and prepares raw API data — filters laps missing duration, calculates stint lap counts, and builds a driver-to-team-colour mapping for the charts.

**`app/visualizer.py`** builds the three Plotly figures: a lap time line chart, a horizontal tire strategy bar chart, and a pit stop duration bar chart. All use driver team colours and custom hover templates.

## 💡 Ideas for Extension

- Add tire degradation trend lines
- Compare qualifying vs race pace
- Highlight fastest lap per driver
- Sector time breakdown charts
- MQTT/WebSocket integration for sub-30s live updates
