
# Crowd Safety Monitor

Estimates crowd density per zone (bridges, entrances, exits, bathing areas), flags overcrowding, predicts when a zone will turn red, and alerts authorities.

## Architecture
Camera video -> `count_video.py` (YOLOv8 people counter) -> POST /api/count -> `app.py` (FastAPI: density, risk, trend, alerts, SQLite) -> dashboard (`static/index.html`) and optional SMS (Twilio).
Without a camera, the backend simulates crowds so the dashboard always has data.

## Logic
Density = people / area (m2). Under 2 green, 2 to 4 yellow, above 4 red.
Minutes to red = (red limit - people now) / net inflow per minute.
Example: 10 m x 4 m bridge = 40 m2, red limit 160. 120 people with +20/min net reaches red in 2 minutes.

## Run
1. `pip install -r requirements.txt`
2. `uvicorn app:app --reload` then open http://127.0.0.1:8000
3. Click "Simulate surge on the bridge" to see yellow, early warning, then red alerts.
4. Real counting (new terminal): `python count_video.py crowd.mp4 --zone Bridge`
5. `static/demo.html` is a standalone demo that needs no backend.

## API
GET /api/zones, GET /api/alerts, POST /api/count {zone, count}, POST /api/simulate/surge, POST /api/simulate/relief



## Limits
Prototype. Camera counts need per-site calibration; zone areas and thresholds should be set with local safety authorities. Dense crowds need a density-map model instead of YOLO.

