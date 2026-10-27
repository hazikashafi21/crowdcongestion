"""Fallback people counter using only OpenCV (no PyTorch needed).
Less accurate than YOLO, but works when PyTorch fails on Windows.
Run (backend must be running):  python count_video_hog.py crowd.mp4 --zone Bridge
"""
import argparse, json, time, urllib.request, cv2
from crowd_monitor import ZONES, density, risk

p = argparse.ArgumentParser()
p.add_argument("video"); p.add_argument("--zone", required=True, choices=list(ZONES))
p.add_argument("--api", default="http://127.0.0.1:8000")
a = p.parse_args()
l, w, _ = ZONES[a.zone]; area = l * w
cap = cv2.VideoCapture(int(a.video) if a.video.isdigit() else a.video)
hog = cv2.HOGDescriptor(); hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
col = {"GREEN": (0, 160, 0), "YELLOW": (0, 190, 255), "RED": (0, 0, 220)}

def send(n):
    req = urllib.request.Request(a.api + "/api/count", json.dumps({"zone": a.zone, "count": n}).encode(),
                                 {"Content-Type": "application/json"})
    try: urllib.request.urlopen(req, timeout=2)
    except Exception as e: print("Backend not reachable:", e)

last = 0
while True:
    ok, frame = cap.read()
    if not ok: cap.set(cv2.CAP_PROP_POS_FRAMES, 0); continue
    frame = cv2.resize(frame, (800, 450))
    boxes, _ = hog.detectMultiScale(frame, winStride=(8, 8), padding=(8, 8), scale=1.05)
    n = len(boxes); d = density(n, area); s = risk(d)
    for (x, y, bw, bh) in boxes: cv2.rectangle(frame, (x, y), (x + bw, y + bh), col[s], 2)
    cv2.putText(frame, f"{a.zone}: {n} people  {d:.1f}/m2  {s}", (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.9, col[s], 2)
    if time.time() - last >= 1: send(n); last = time.time()
    cv2.imshow("Crowd Safety Monitor", frame)
    if cv2.waitKey(1) == 27: break
