#!/usr/bin/env python3
"""
SkyWatch — Anomaly Detector
============================
Analyzes flight trajectories to find unusual patterns.

7 Detection Algorithms:
  1. Circular / Holding Patterns
  2. Altitude Anomalies (sudden drops / climbs)
  3. Loitering (small area, long duration)
  4. Zigzag / Heading Reversals
  5. Path Inefficiency (overly indirect routes)
  6. Speed Anomalies (abnormally fast or slow)
  7. Sustained Low-Altitude Flight (mid-flight)

Usage:
    python detect_anomalies.py
"""

import json
import math
import os
from datetime import datetime, timezone
from collections import defaultdict

import config


# ── Utilities ────────────────────────────────────────────────

def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points (km)."""
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(min(1.0, math.sqrt(a)))


def bearing_diff(h1, h2):
    """Absolute difference between two headings (0–180°)."""
    d = abs(h1 - h2) % 360
    return min(d, 360 - d)


def bearing(lat1, lon1, lat2, lon2):
    """Initial bearing (forward azimuth) from point 1 to point 2 in degrees (0–360°)."""
    r_lat1, r_lat2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    y = math.sin(dlon) * math.cos(r_lat2)
    x = math.cos(r_lat1) * math.sin(r_lat2) - math.sin(r_lat1) * math.cos(r_lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def m_to_ft(m):
    return (m or 0) * 3.28084


# ── Detector Class ───────────────────────────────────────────

class AnomalyDetector:
    """Runs all anomaly detection algorithms on collected flight tracks."""

    def __init__(self):
        self.anomalies = []
        self.stats = defaultdict(int)

    # ── Load Data ────────────────────────────────────────────

    def load_tracks(self):
        path = os.path.join(config.DATA_DIR, "tracks.json")
        if not os.path.exists(path):
            print("❌ No track data found. Run collect_data.py first.")
            return []
        with open(path) as f:
            tracks = json.load(f)
        print(f"📂 Loaded {len(tracks)} flight tracks")
        return tracks

    # ── 1. Circular / Holding Patterns ───────────────────────

    def detect_circular(self, track):
        wps = track["waypoints"]
        if len(wps) < 10:
            return None

        loops = 0
        for i in range(len(wps)):
            for j in range(i + 5, len(wps)):
                dist = haversine_km(wps[i]["lat"], wps[i]["lon"],
                                    wps[j]["lat"], wps[j]["lon"])
                dt = abs(wps[j]["time"] - wps[i]["time"])
                if dist < config.CIRCULAR_RETURN_DISTANCE_KM and dt > 120:
                    loops += 1
                    break  # one match per origin point

        if loops < config.CIRCULAR_MIN_LOOPS:
            return None

        lats = [w["lat"] for w in wps]
        lons = [w["lon"] for w in wps]
        bbox = haversine_km(min(lats), min(lons), max(lats), max(lons))
        dur = (wps[-1]["time"] - wps[0]["time"]) / 60

        # Holding patterns and orbits are geographically confined (under 80 km)
        if bbox > getattr(config, 'CIRCULAR_MAX_BBOX_KM', 80.0):
            return None

        return {
            "type": "circular",
            "score": min(100, loops * 15),
            "loops": loops,
            "bbox_km": round(bbox, 1),
            "duration_min": round(dur, 1),
            "details": (
                f"Completed {loops} loops within {bbox:.1f} km area "
                f"over {dur:.0f} minutes"
            ),
        }

    # ── 2. Altitude Anomalies ────────────────────────────────

    def detect_altitude_anomaly(self, track):
        wps = track["waypoints"]
        events = []

        for i in range(len(wps)):
            for j in range(i + 1, min(i + 10, len(wps))):
                alt_i = m_to_ft(wps[i]["alt"])
                alt_j = m_to_ft(wps[j]["alt"])
                dt = abs(wps[j]["time"] - wps[i]["time"])
                if dt == 0 or dt > config.ALTITUDE_DROP_TIME_SEC:
                    continue

                change = alt_j - alt_i
                # Only flag severe rapid drops (dives), never normal climbs
                if change < -config.ALTITUDE_DROP_THRESHOLD_FT:
                    rate = abs(change) / dt * 60
                    if rate >= getattr(config, 'ALTITUDE_MIN_RATE_FPM', 3500):
                        events.append(dict(dir="drop", change=round(change),
                                           dt=dt, alt0=round(alt_i), alt1=round(alt_j),
                                           lat=wps[i]["lat"], lon=wps[i]["lon"]))

        if not events:
            return None

        worst = max(events, key=lambda e: abs(e["change"]))
        rate = abs(worst["change"]) / max(worst["dt"], 1) * 60
        label = "Emergency descent / dive:"

        return {
            "type": "altitude",
            "score": min(100, abs(worst["change"]) / 100),
            "events": len(events),
            "worst_change_ft": worst["change"],
            "worst_time_sec": worst["dt"],
            "rate_ft_per_min": round(rate),
            "lat": worst["lat"],
            "lon": worst["lon"],
            "details": (
                f"{label} {abs(worst['change']):,} ft in {worst['dt']}s "
                f"({rate:,.0f} ft/min) — "
                f"from {worst['alt0']:,} ft to {worst['alt1']:,} ft"
            ),
        }

    # ── 3. Loitering ────────────────────────────────────────

    def detect_loiter(self, track):
        wps = track["waypoints"]
        if len(wps) < 5:
            return None

        lats = [w["lat"] for w in wps]
        lons = [w["lon"] for w in wps]
        bbox = haversine_km(min(lats), min(lons), max(lats), max(lons))
        dur = (wps[-1]["time"] - wps[0]["time"]) / 60

        if bbox >= config.LOITER_MAX_BBOX_KM or dur < config.LOITER_MIN_DURATION_MIN:
            return None

        clat = sum(lats) / len(lats)
        clon = sum(lons) / len(lons)
        radius_km = bbox / 2.0
        area_sq_km = math.pi * (radius_km ** 2)

        # Average ground speed during loiter
        speeds = []
        for i in range(1, len(wps)):
            dt = wps[i]["time"] - wps[i - 1]["time"]
            if dt > 0:
                d = haversine_km(wps[i - 1]["lat"], wps[i - 1]["lon"], wps[i]["lat"], wps[i]["lon"])
                kt = (d / (dt / 3600)) * 0.539957
                if 5 < kt < 700:
                    speeds.append(kt)
        avg_speed_kt = sum(speeds) / len(speeds) if speeds else 0

        score = min(100, (dur / config.LOITER_MIN_DURATION_MIN) * 25 + (1 / max(bbox, 0.1)) * 30)

        return {
            "type": "loiter",
            "score": min(100, score),
            "bbox_km": round(bbox, 1),
            "area_sq_km": round(area_sq_km, 1),
            "duration_min": round(dur, 1),
            "avg_speed_kt": round(avg_speed_kt, 1),
            "center_lat": round(clat, 4),
            "center_lon": round(clon, 4),
            "details": (
                f"Sustained airborne loiter/patrol: Confined to {bbox:.1f} km bounding perimeter "
                f"(~{area_sq_km:.0f} km² zone) for {dur:.1f} min at avg {avg_speed_kt:.0f} kt "
                f"(GeoCenter: {clat:.4f}°, {clon:.4f}°)"
            ),
        }

    # ── 4. Zigzag / Heading Reversals ────────────────────────

    def detect_zigzag(self, track):
        wps = track["waypoints"]
        if len(wps) < 8:
            return None

        # Build aeronautical flight legs by sampling distance >= 0.8 km or dt >= 30s
        legs = []
        last = wps[0]
        for wp in wps[1:]:
            d = haversine_km(last["lat"], last["lon"], wp["lat"], wp["lon"])
            dt = wp["time"] - last["time"]
            if d >= 0.8 or dt >= 30:
                brg = bearing(last["lat"], last["lon"], wp["lat"], wp["lon"])
                legs.append({"bearing": brg, "dist": d, "dt": dt, "lat": wp["lat"], "lon": wp["lon"]})
                last = wp

        if len(legs) < 3:
            return None

        reversals = []
        for i in range(1, len(legs)):
            diff = bearing_diff(legs[i - 1]["bearing"], legs[i]["bearing"])
            if diff >= config.ZIGZAG_REVERSAL_ANGLE:
                reversals.append({
                    "from_brg": round(legs[i - 1]["bearing"], 1),
                    "to_brg": round(legs[i]["bearing"], 1),
                    "delta_deg": round(diff, 1),
                    "lat": legs[i]["lat"],
                    "lon": legs[i]["lon"],
                })

        if len(reversals) < config.ZIGZAG_MIN_REVERSALS:
            return None

        dur = (wps[-1]["time"] - wps[0]["time"]) / 60
        avg_turn = sum(r["delta_deg"] for r in reversals) / len(reversals)
        sample_turns = " ➔ ".join(f"{r['from_brg']:.0f}°→{r['to_brg']:.0f}° (Δ{r['delta_deg']:.0f}°)" for r in reversals[:3])
        if len(reversals) > 3:
            sample_turns += f" (+{len(reversals)-3} more)"

        pattern_desc = "Reciprocal Survey / Swath Grid" if avg_turn > 140 else "Tactical Maneuver / S-Turn Vector"

        return {
            "type": "zigzag",
            "score": min(100, len(reversals) * 12 + (avg_turn / 3)),
            "reversals": len(reversals),
            "avg_turn_deg": round(avg_turn, 1),
            "duration_min": round(dur, 1),
            "reversal_sequence": sample_turns,
            "pattern_desc": pattern_desc,
            "lat": reversals[0]["lat"],
            "lon": reversals[0]["lon"],
            "details": (
                f"{len(reversals)} sharp heading reversals (avg turn {avg_turn:.0f}°): {sample_turns} "
                f"across {len(legs)} flight legs over {dur:.0f} min [{pattern_desc}]"
            ),
        }

    # ── 5. Path Inefficiency ─────────────────────────────────

    def detect_path_inefficiency(self, track):
        wps = track["waypoints"]
        if len(wps) < 5:
            return None

        direct = haversine_km(wps[0]["lat"], wps[0]["lon"],
                              wps[-1]["lat"], wps[-1]["lon"])
        if direct < 5:  # Evaluate any flight with >= 5km displacement
            return None

        actual = sum(
            haversine_km(wps[i - 1]["lat"], wps[i - 1]["lon"],
                         wps[i]["lat"], wps[i]["lon"])
            for i in range(1, len(wps))
        )
        if actual == 0:
            return None

        ratio = actual / direct
        if ratio < config.PATH_EFFICIENCY_THRESHOLD:
            return None

        excess_km = actual - direct
        efficiency_pct = (direct / actual) * 100

        return {
            "type": "path_inefficiency",
            "score": min(100, (ratio - 1) * 25),
            "ratio": round(ratio, 2),
            "direct_km": round(direct, 1),
            "actual_km": round(actual, 1),
            "excess_km": round(excess_km, 1),
            "efficiency_pct": round(efficiency_pct, 1),
            "details": (
                f"High-deviation flight path: {ratio:.2f}× direct distance "
                f"({actual:.1f} km flown vs {direct:.1f} km direct, +{excess_km:.1f} km excess, "
                f"{efficiency_pct:.1f}% great-circle efficiency)"
            ),
        }

    # ── 6. Speed Anomaly ─────────────────────────────────────

    def detect_speed_anomaly(self, track):
        wps = track["waypoints"]
        if len(wps) < 5:
            return None

        speeds = []
        for i in range(1, len(wps)):
            dt = wps[i]["time"] - wps[i - 1]["time"]
            if dt <= 0:
                continue
            d = haversine_km(wps[i - 1]["lat"], wps[i - 1]["lon"],
                             wps[i]["lat"], wps[i]["lon"])
            kt = (d / (dt / 3600)) * 0.539957  # km/h → knots
            if kt > 0:
                speeds.append(dict(kt=kt, lat=wps[i]["lat"], lon=wps[i]["lon"]))

        if not speeds:
            return None

        mx = max(speeds, key=lambda s: s["kt"])
        mn = min(speeds, key=lambda s: s["kt"])
        avg = sum(s["kt"] for s in speeds) / len(speeds)

        if mx["kt"] > config.SPEED_ANOMALY_HIGH_KT:
            return {
                "type": "speed",
                "score": min(100, (mx["kt"] - config.SPEED_ANOMALY_HIGH_KT) / 5),
                "direction": "fast",
                "max_speed_kt": round(mx["kt"]),
                "avg_speed_kt": round(avg),
                "lat": mx["lat"], "lon": mx["lon"],
                "details": f"Extreme speed: {mx['kt']:.0f} kt (avg {avg:.0f} kt)",
            }

        if avg < config.SPEED_ANOMALY_LOW_KT and avg > 5:
            return {
                "type": "speed",
                "score": min(100, (config.SPEED_ANOMALY_LOW_KT - avg) * 2),
                "direction": "slow",
                "avg_speed_kt": round(avg),
                "min_speed_kt": round(mn["kt"]),
                "lat": mn["lat"], "lon": mn["lon"],
                "details": f"Unusually slow: average {avg:.0f} kt",
            }

        return None

    # ── 7. Sustained Low Altitude ────────────────────────────

    def detect_low_altitude(self, track):
        wps = track["waypoints"]
        if len(wps) < 10:
            return None

        # Ignore first/last 20 % (takeoff / landing)
        s = len(wps) // 5
        e = len(wps) * 4 // 5
        mid = wps[s:e]
        if len(mid) < 5:
            return None

        streak, best, best_start = 0, 0, None
        start_t = None
        for wp in mid:
            alt = m_to_ft(wp.get("alt", 10_000))
            if 0 < alt < config.LOW_ALTITUDE_THRESHOLD_FT:
                if streak == 0:
                    start_t = wp["time"]
                streak += 1
                if streak > best:
                    best = streak
                    best_start = start_t
            else:
                streak = 0

        if best < 5 or best_start is None:
            return None

        dur = mid[-1]["time"] - best_start
        if dur < config.LOW_ALTITUDE_DURATION_SEC:
            return None

        avg_alt = sum(m_to_ft(w.get("alt", 0)) for w in mid) / len(mid)

        return {
            "type": "low_altitude",
            "score": min(100, best * 8),
            "avg_alt_ft": round(avg_alt),
            "duration_sec": dur,
            "waypoints_low": best,
            "details": (
                f"Sustained low-altitude flight ~{avg_alt:.0f} ft for "
                f"{dur / 60:.0f} min (mid-flight, not takeoff/landing)"
            ),
        }

    # ── Orchestration ────────────────────────────────────────

    def analyze_track(self, track):
        """Run every detector on one track; return list of hits."""
        detectors = [
            self.detect_circular,
            self.detect_altitude_anomaly,
            self.detect_loiter,
            self.detect_zigzag,
            self.detect_path_inefficiency,
            self.detect_speed_anomaly,
            self.detect_low_altitude,
        ]
        hits = []
        for fn in detectors:
            try:
                res = fn(track)
            except Exception:
                continue
            if res is None:
                continue
            res["icao24"] = track["icao24"]
            res["callsign"] = track.get("callsign", "")
            res["origin_country"] = track.get("origin_country", "")
            res["squawk"] = track.get("squawk", "")
            res["waypoints"] = track["waypoints"]
            hits.append(res)
            self.stats[res["type"]] += 1
        return hits

    def analyze_all(self):
        """Main analysis pipeline."""
        tracks = self.load_tracks()
        if not tracks:
            return []

        print(f"\n🔍 Running 7 anomaly detection algorithms on {len(tracks)} tracks …\n")

        all_hits = []
        analyzed = 0
        for t in tracks:
            if len(t.get("waypoints", [])) < config.MIN_WAYPOINTS:
                continue
            analyzed += 1
            all_hits.extend(self.analyze_track(t))

        all_hits.sort(key=lambda x: x["score"], reverse=True)

        self._save(all_hits)
        self._print_summary(all_hits, analyzed)
        return all_hits

    # ── Output ───────────────────────────────────────────────

    def _save(self, anomalies):
        # Full (with waypoints — for visualization)
        full_path = os.path.join(config.RESULTS_DIR, "anomalies.json")
        with open(full_path, "w") as f:
            json.dump(anomalies, f)

        # Summary (no waypoints — human-readable)
        summary = [{k: v for k, v in a.items() if k != "waypoints"} for a in anomalies]
        with open(os.path.join(config.RESULTS_DIR, "anomalies_summary.json"), "w") as f:
            json.dump(summary, f, indent=2)

        # Text report
        self._write_report(anomalies)

    def _write_report(self, anomalies):
        rpath = os.path.join(config.RESULTS_DIR, "report.txt")
        with open(rpath, "w") as f:
            f.write("=" * 70 + "\n")
            f.write("  SKYWATCH — Flight Anomaly Detection Report\n")
            f.write(f"  Generated : {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}\n")
            f.write(f"  Region    : {config.REGIONS[config.ACTIVE_REGION]['name']}\n")
            f.write("=" * 70 + "\n\n")

            if not anomalies:
                f.write("No anomalies detected.\n")
                return

            by_type = defaultdict(list)
            for a in anomalies:
                by_type[a["type"]].append(a)

            f.write(f"TOTAL: {len(anomalies)} anomalies across "
                    f"{len(by_type)} categories\n")

            for atype, items in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
                f.write(f"\n{'─' * 55}\n")
                f.write(f"  {atype.upper().replace('_', ' ')}  ({len(items)} found)\n")
                f.write(f"{'─' * 55}\n\n")
                for i, it in enumerate(items[:10], 1):
                    cs = it.get("callsign") or "N/A"
                    f.write(f"  #{i}  [{cs}]  ICAO {it['icao24']}  "
                            f"| {it.get('origin_country', '?')}  "
                            f"| Score {it['score']:.0f}/100\n")
                    f.write(f"       {it['details']}\n\n")

    def _print_summary(self, anomalies, total):
        print(f"\n{'=' * 60}")
        print(f"  🔍 ANOMALY DETECTION RESULTS")
        print(f"{'=' * 60}")
        print(f"   Tracks analyzed : {total}")
        print(f"   Anomalies found : {len(anomalies)}")
        print()

        if not anomalies:
            print("   No anomalies detected. Try loosening thresholds in config.py")
            return

        emoji = {
            "circular": "🔄", "altitude": "📉", "loiter": "📍",
            "zigzag": "⚡", "path_inefficiency": "🔀",
            "speed": "💨", "low_altitude": "⬇️",
        }
        print("   Breakdown:")
        for t, c in sorted(self.stats.items(), key=lambda kv: -kv[1]):
            print(f"     {emoji.get(t, '❓')} {t.replace('_', ' ').title()}: {c}")

        print(f"\n   🏆 Top 5 Most Anomalous Flights:")
        print(f"   {'─' * 50}")
        seen, shown = set(), 0
        for a in anomalies:
            if a["icao24"] in seen:
                continue
            seen.add(a["icao24"])
            shown += 1
            cs = a.get("callsign") or "???"
            print(f"   {shown}. [{cs}] Score {a['score']:.0f}/100 "
                  f"— {a['type'].replace('_', ' ').title()}")
            print(f"      {a['details']}")
            if shown >= 5:
                break

        print(f"\n   💾 Results → {config.RESULTS_DIR}/")
        print(f"   Next step  → python visualize.py")


# ── Main ─────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  🔍 SkyWatch — Anomaly Detector")
    print("=" * 60)
    AnomalyDetector().analyze_all()


if __name__ == "__main__":
    main()
