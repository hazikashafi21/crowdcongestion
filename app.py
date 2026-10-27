"""Crowd Safety Monitor backend (FastAPI + SQLite).
Run:  uvicorn app:app --reload     then open http://127.0.0.1:8000
Zones use simulated data until a camera counter (count_video.py) starts posting real counts.
"""
import os, time, random, sqlite3, threading
from collections import deque
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from crowd_monitor import ZONES, RED_LIMIT_COUNT, density, risk, minutes_to_red

HERE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(HERE, "crowd.db")
lock = threading.Lock()

def q(sql, args=(), fetch=False):
    c = sqlite3.connect(DB)
    try:
        rows = c.execute(sql, args).fetchall() if fetch else c.execute(sql, args) and None
        c.commit(); return rows
    finally:
        c.close()

q("create table if not exists alerts(ts text, zone text, level text, message text)")
q("create table if not exists readings(ts text, zone text, people int, density real, status text)")

S = {z: {"count": int(l * w * 0.8), "hist": deque(maxlen=120), "status": "GREEN",
         "warned": False, "real": 0.0} for z, (l, w, _) in ZONES.items()}
SURGE = {"on": False}

def net_per_min(z):
    now = time.time(); h = [p for p in S[z]["hist"] if now - p[0] <= 30]
    if len(h) < 2 or h[-1][0] == h[0][0]: return 0.0
    return (h[-1][1] - h[0][1]) / (h[-1][0] - h[0][0]) * 60

def sms(text):
    """Optional. Set TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM, ALERT_TO to enable."""
    try:
        from twilio.rest import Client
        Client(os.environ["TWILIO_SID"], os.environ["TWILIO_TOKEN"]).messages.create(
            body=text, from_=os.environ["TWILIO_FROM"], to=os.environ["ALERT_TO"])
    except Exception:
        pass

def log_alert(zone, level, msg):
    q("insert into alerts values(?,?,?,?)", (datetime.now().strftime("%H:%M:%S"), zone, level, msg))
    print(f"[{level}] {msg}")
    if level == "RED": sms(msg)

def update(zone, count, real=False):
    with lock:
        s = S[zone]; l, w, act = ZONES[zone]; now = time.time()
        s["count"] = max(0, count); s["hist"].append((now, s["count"]))
        if real: s["real"] = now
        d = density(s["count"], l * w); st = risk(d)
        eta = minutes_to_red(s["count"], RED_LIMIT_COUNT[zone], net_per_min(zone))
        if st != s["status"] and st != "GREEN":
            log_alert(zone, st, f"{zone} at {d:.1f} people/m2. {act}")
        elif st == "GREEN" and eta is not None and eta <= 3 and not s["warned"]:
            s["warned"] = True
            log_alert(zone, "EARLY WARNING", f"{zone} will turn red in about {eta:.1f} min. {act}")
        if eta is None or eta > 3: s["warned"] = False
        s["status"] = st
        q("insert into readings values(?,?,?,?,?)",
          (datetime.now().isoformat(timespec="seconds"), zone, s["count"], round(d, 2), st))

def simulate():
    while True:
        time.sleep(2)
        for z in ZONES:
            if time.time() - S[z]["real"] < 10: continue       # real camera data wins
            inn = random.randint(0, 6) + (4 if SURGE["on"] and z == "Bridge" else 0)
            update(z, S[z]["count"] + inn - random.randint(0, 6))

threading.Thread(target=simulate, daemon=True).start()
app = FastAPI(title="Crowd Safety Monitor")

class Count(BaseModel):
    zone: str
    count: int

@app.post("/api/count")
def post_count(c: Count):
    if c.zone not in ZONES: raise HTTPException(404, "Unknown zone")
    update(c.zone, c.count, real=True); return {"ok": True}

@app.get("/api/zones")
def zones():
    out = []
    for z, (l, w, act) in ZONES.items():
        s = S[z]; d = density(s["count"], l * w); n = net_per_min(z)
        eta = minutes_to_red(s["count"], RED_LIMIT_COUNT[z], n)
        out.append({"zone": z, "area": l * w, "count": s["count"], "density": round(d, 2),
                    "status": risk(d), "net_per_min": round(n), "action": act,
                    "eta": None if eta is None else round(eta, 1),
                    "source": "camera" if time.time() - s["real"] < 10 else "simulated"})
    return out

@app.get("/api/alerts")
def alerts():
    rows = q("select ts, zone, level, message from alerts order by rowid desc limit 20", fetch=True)
    return [dict(ts=r[0], zone=r[1], level=r[2], message=r[3]) for r in rows]

@app.post("/api/simulate/surge")
def surge(): SURGE["on"] = True; return {"ok": True}

@app.post("/api/simulate/relief")
def relief():
    SURGE["on"] = False
    for z, (l, w, _) in ZONES.items(): update(z, int(l * w * 0.8))
    return {"ok": True}

app.mount("/", StaticFiles(directory=os.path.join(HERE, "static"), html=True), name="static")
