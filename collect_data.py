#!/usr/bin/env python3
"""
SkyWatch — Flight Data Collector
=================================
Downloads real-time ADS-B flight data from OpenSky Network.
Collects flight trajectories for anomaly analysis.

Usage:
    python collect_data.py
"""

import json
import os
import sys
import time
import requests
from datetime import datetime, timezone
from pathlib import Path

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

import config

# ── API ──────────────────────────────────────────────────────
BASE_URL = "https://opensky-network.org/api"


def _simple_progress(iterable, desc="", total=None):
    """Fallback progress bar when tqdm is not installed."""
    if total is None:
        try:
            total = len(iterable)
        except TypeError:
            total = None
    for i, item in enumerate(iterable, 1):
        pct = f" ({i}/{total})" if total else f" ({i})"
        print(f"\r   {desc}{pct}", end="", flush=True)
        yield item
    print()


def progress(iterable, **kwargs):
    """Use tqdm if available, otherwise simple fallback."""
    if HAS_TQDM:
        return tqdm(iterable, **kwargs)
    return _simple_progress(iterable, desc=kwargs.get("desc", ""), total=kwargs.get("total"))


class FlightCollector:
    """Collects flight data from OpenSky Network REST API."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "SkyWatch-Anomaly-Detector/1.0"})

        if config.OPENSKY_USERNAME and config.OPENSKY_PASSWORD:
            self.session.auth = (config.OPENSKY_USERNAME, config.OPENSKY_PASSWORD)
            self.authenticated = True
        else:
            self.authenticated = False

        self.region = config.REGIONS[config.ACTIVE_REGION]

        # Create output directories
        os.makedirs(config.DATA_DIR, exist_ok=True)
        os.makedirs(config.TRACKS_DIR, exist_ok=True)
        os.makedirs(config.RESULTS_DIR, exist_ok=True)

    # ── HTTP Helper ──────────────────────────────────────────
    def _api_call(self, endpoint, params=None, retries=None):
        """Make an API call with automatic retry + back-off."""
        if retries is None:
            retries = config.MAX_RETRIES
        url = f"{BASE_URL}{endpoint}"

        for attempt in range(retries):
            try:
                resp = self.session.get(
                    url, params=params, timeout=config.REQUEST_TIMEOUT_SEC
                )
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 429:
                    wait = config.RETRY_DELAY_SEC * (attempt + 1) * 2
                    print(f"\n  ⏳ Rate-limited. Waiting {wait}s …")
                    time.sleep(wait)
                elif resp.status_code == 404:
                    return None
                else:
                    print(f"\n  ⚠ HTTP {resp.status_code} on {endpoint}")
                    time.sleep(config.RETRY_DELAY_SEC)
            except requests.exceptions.Timeout:
                print(f"\n  ⏱ Timeout (attempt {attempt+1}/{retries})")
                time.sleep(config.RETRY_DELAY_SEC)
            except requests.exceptions.ConnectionError:
                print(f"\n  🔌 Connection error (attempt {attempt+1}/{retries})")
                time.sleep(config.RETRY_DELAY_SEC * 2)
            except Exception as exc:
                print(f"\n  ❌ {exc}")
                time.sleep(config.RETRY_DELAY_SEC)
        return None

    # ── Step 1: Get aircraft currently in the air ────────────
    def get_current_aircraft(self):
        """Fetch all airborne aircraft over the active region."""
        print(f"\n🛰  Scanning airspace: {self.region['name']}")
        auth_label = "✅ Registered user" if self.authenticated else "⚠ Anonymous (slower limits)"
        print(f"   Auth: {auth_label}")

        params = {
            "lamin": self.region["lamin"],
            "lomin": self.region["lomin"],
            "lamax": self.region["lamax"],
            "lomax": self.region["lomax"],
        }

        data = self._api_call("/states/all", params=params)
        if not data or "states" not in data or not data["states"]:
            print("   ❌ No aircraft found. The region may have low coverage, or try later.")
            return []

        aircraft = []
        for s in data["states"]:
            # Skip on-ground or missing position
            if s[8] or s[5] is None or s[6] is None:
                continue
            aircraft.append({
                "icao24":         s[0],
                "callsign":       (s[1] or "").strip(),
                "origin_country": s[2],
                "longitude":      s[5],
                "latitude":       s[6],
                "altitude":       s[7],
                "velocity":       s[9],
                "heading":        s[10],
                "vertical_rate":  s[11],
                "squawk":         s[14],
            })

        print(f"   ✅ Found {len(aircraft)} aircraft in the air")
        return aircraft

    # ── Step 2: Download trajectory for one aircraft ─────────
    def get_track(self, icao24):
        """Download the trajectory/track of a single aircraft."""
        data = self._api_call("/tracks/all", params={"icao24": icao24, "time": 0})
        if not data or "path" not in data or not data["path"]:
            return None

        waypoints = []
        for wp in data["path"]:
            if wp[1] is not None and wp[2] is not None:
                waypoints.append({
                    "time":      wp[0],
                    "lat":       wp[1],
                    "lon":       wp[2],
                    "alt":       wp[3] if wp[3] is not None else 0,
                    "heading":   wp[4] if wp[4] is not None else 0,
                    "on_ground": wp[5],
                })

        if len(waypoints) < config.MIN_WAYPOINTS:
            return None

        return {
            "icao24":    data.get("icao24", icao24),
            "callsign":  (data.get("callsign") or "").strip(),
            "startTime": data.get("startTime"),
            "endTime":   data.get("endTime"),
            "waypoints": waypoints,
        }

    # ── Step 3: Bulk collection pipeline ─────────────────────
    def collect_all_tracks(self):
        """Main pipeline: scan airspace → download tracks."""
        aircraft = self.get_current_aircraft()
        if not aircraft:
            return []

        # Resume support: load previously saved tracks
        save_path = os.path.join(config.DATA_DIR, "tracks.json")
        existing = {}
        if os.path.exists(save_path):
            try:
                with open(save_path) as f:
                    existing = {t["icao24"]: t for t in json.load(f)}
                print(f"   📂 Resuming — {len(existing)} tracks already on disk")
            except Exception:
                pass

        needed = max(0, config.MAX_FLIGHTS - len(existing))
        if needed == 0:
            print(f"   ✅ Already have {len(existing)} tracks (target: {config.MAX_FLIGHTS}).")
            return list(existing.values())

        # Candidates not yet downloaded
        candidates = [a for a in aircraft if a["icao24"] not in existing]
        print(f"   🎯 {len(candidates)} new candidates available in current live scan")

        # Stratify to ensure maximum variety of genuine flight behavior:
        # 1. Low altitude (patrol, survey, flight training, helicopters)
        low_alt = [a for a in candidates if a.get("altitude") is not None and a["altitude"] < 4000]
        # 2. Maneuvering / Slow / Vertical (helicopters, holding, agile)
        maneuver = [a for a in candidates if a not in low_alt and ((a.get("velocity") or 0) < 95 or abs(a.get("vertical_rate") or 0) > 4)]
        # 3. High-altitude / transit flights (transcon, airliners)
        transit = [a for a in candidates if a not in low_alt and a not in maneuver]

        print(f"   📊 Stratified candidates: {len(low_alt)} low-altitude/patrol, {len(maneuver)} maneuvering/holding, {len(transit)} transit")

        # Interleave to ensure balanced, realistic sample
        targeted = []
        i_low, i_man, i_tran = 0, 0, 0
        while len(targeted) < needed and (i_low < len(low_alt) or i_man < len(maneuver) or i_tran < len(transit)):
            if i_low < len(low_alt):
                targeted.append(low_alt[i_low])
                i_low += 1
            if len(targeted) >= needed: break
            if i_man < len(maneuver):
                targeted.append(maneuver[i_man])
                i_man += 1
            if len(targeted) >= needed: break
            if i_tran < len(transit):
                targeted.append(transit[i_tran])
                i_tran += 1

        print(
            f"\n📡 Downloading trajectories for {len(targeted)} selected aircraft …"
        )
        est_min = len(targeted) * config.TRACK_DELAY_SEC / 60
        print(f"   Estimated time: ~{est_min:.1f} minutes\n")

        tracks = list(existing.values())
        new_ok, failures = 0, 0

        for ac in progress(targeted, desc="   Downloading", total=len(targeted)):
            icao24 = ac["icao24"]

            if icao24 in existing:
                continue  # already have it

            track = self.get_track(icao24)
            if track:
                track["origin_country"] = ac.get("origin_country", "")
                track["squawk"] = ac.get("squawk", "")
                tracks.append(track)
                existing[icao24] = track
                new_ok += 1
            else:
                failures += 1

            time.sleep(config.TRACK_DELAY_SEC)

            # Checkpoint every 50 new tracks
            if new_ok > 0 and new_ok % 50 == 0:
                self._save(tracks, save_path)

        self._save(tracks, save_path)

        # ── Summary ──
        print(f"\n{'='*55}")
        print(f"  📊 Collection Summary")
        print(f"{'='*55}")
        print(f"   Total tracks on disk : {len(tracks)}")
        print(f"   New downloads        : {new_ok}")
        print(f"   Skipped / no data    : {failures}")
        print(f"   Saved to             : {save_path}")
        return tracks

    @staticmethod
    def _save(tracks, path):
        with open(path, "w") as f:
            json.dump(tracks, f)


# ── Main ─────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  🛩  SkyWatch — Flight Data Collector")
    print("=" * 60)

    collector = FlightCollector()
    tracks = collector.collect_all_tracks()

    if tracks:
        print(f"\n✅ Data ready!  Next step → python detect_anomalies.py")
    else:
        print(f"\n❌ No tracks collected. Check credentials / connectivity.")


if __name__ == "__main__":
    main()
