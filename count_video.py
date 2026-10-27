"""Count people in a video and send the count to the backend.
Run (backend must be running):  python count_video.py crowd.mp4 --zone Bridge
Use one terminal per zone/camera. Esc quits.
"""
import argparse, json, time, urllib.request, cv2
from ultralytics import YOLO
from crowd_monitor import ZONES, density, risk

p = argparse.ArgumentParser()
p.add_argument("video"); p.add_argument("--zone", required=True, choices=list(ZONES))
p.add_argument("--api", default="http://127.0.0.1:8000")
a = p.parse_args()
l, w, _ = ZONES[a.zone]; area = l * w
model = YOLO("yolov8n.pt"); cap = cv2.VideoCapture(a.video)
col = {"GREEN": (0, 160, 0), "YELLOW": (0, 190, 255), "RED": (0, 0, 220)}

def send(n):
    req = urllib.request.Request(a.api + "/api/count", json.dumps({"zone": a.zone, "count": n}).encode(),
                                 {"Content-Type": "application/json"})
    try: urllib.request.urlopen(req, timeout=2)
    except Exception as e: print("Backend not reachable:", e)

last = 0
while True:
    ok, frame = cap.read()
    if not ok: cap.set(cv2.CAP_PROP_POS_FRAMES, 0); continue     # loop the video for demos
    res = model(frame, classes=[0], verbose=False)[0]; n = len(res.boxes)
    d = density(n, area); s = risk(d)
    for b in res.boxes.xyxy:
        x1, y1, x2, y2 = map(int, b); cv2.rectangle(frame, (x1, y1), (x2, y2), col[s], 1)
    cv2.putText(frame, f"{a.zone}: {n} people  {d:.1f}/m2  {s}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, col[s], 2)
    if time.time() - last >= 1: send(n); last = time.time()
    cv2.imshow("Crowd Safety Monitor", frame)
    if cv2.waitKey(1) == 27: break
