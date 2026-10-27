"""Crowd Safety Monitor - core logic (no external libraries needed).
Run:  python crowd_monitor.py            -> live console demo + writes crowd_data.csv
"""
import csv, random, time
from collections import deque

# name: (length_m, width_m, safe_action)
ZONES = {
    "Bridge":        (10, 4,  "Stop entry at bridge head; allow one-way flow"),
    "Main Entrance": (12, 6,  "Open extra gate; slow entry with barriers"),
    "Exit B":        (8, 5,   "Clear exit path; redirect crowd from Exit A"),
    "Bathing Ghat":  (20, 10, "Limit bathers; deploy rescue boats and volunteers"),
}
YELLOW, RED = 2.0, 4.0          # people per m2 (common crowd-safety guidance)
RED_LIMIT_COUNT = {}            # filled below: max people before red

for z, (l, w, _) in ZONES.items():
    RED_LIMIT_COUNT[z] = RED * l * w

def density(count, area):
    return count / area

def risk(d):
    return "GREEN" if d < YELLOW else "YELLOW" if d < RED else "RED"

def minutes_to_red(count, limit, net_per_min):
    """Early warning: minutes until the zone crosses the red limit."""
    if count >= limit: return 0.0
    if net_per_min <= 0: return None
    return (limit - count) / net_per_min

def alert(zone, d, status, eta=None):
    msg = f"[{status}] {zone}: {d:.1f} people/m2. Action: {ZONES[zone][2]}"
    if eta is not None: msg += f" (red in ~{eta:.1f} min)"
    print(msg)   # replace with Twilio SMS / Firebase push in production

def simulate(minutes=30, seed=1):
    """Synthetic data: each zone gets entries/exits per minute, with a surge."""
    random.seed(seed)
    state = {z: random.randint(20, 60) for z in ZONES}
    rows, hist = [], {z: deque(maxlen=3) for z in ZONES}
    for t in range(minutes):
        for z, (l, w, _) in ZONES.items():
            surge = 25 if (z == "Bridge" and t >= 10) else 0
            inflow = random.randint(5, 20) + surge
            outflow = random.randint(8, 18)
            state[z] = max(0, state[z] + inflow - outflow)
            d = density(state[z], l * w)
            hist[z].append(inflow - outflow)
            net = sum(hist[z]) / len(hist[z])
            eta = minutes_to_red(state[z], RED_LIMIT_COUNT[z], net)
            rows.append([t, z, l * w, inflow, outflow, state[z], round(d, 2), risk(d)])
            if risk(d) != "GREEN" or (eta is not None and eta <= 3):
                alert(z, d, risk(d), eta)
    return rows

if __name__ == "__main__":
    data = simulate()
    with open("crowd_data.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["minute", "zone", "area_m2", "inflow", "outflow", "people", "density", "status"])
        w.writerows(data)
    print("Saved crowd_data.csv with", len(data), "rows")
