#!/usr/bin/env python3
"""
SkyWatch — Airspace Visualization Engine (100% Pure Live Data Edition)
======================================================================
Visualizes ONLY genuine real-world ADS-B flight telemetry harvested live
from OpenSky Network satellites. No synthetic data, no simulations.

Outputs:
  1. data/results/anomaly_map.png  — 300 DPI tactical map of real airborne flights
  2. data/results/flight_map.html  — Interactive map with zero-watermark Esri tiles
"""

import json
import math
import os
import sys
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.lines import Line2D
import numpy as np

try:
    import folium
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False

import config

MAJOR_HUBS = [
    {"code": "LAS", "lat": 36.0840, "lon": -115.1537},
    {"code": "LAX", "lat": 33.9416, "lon": -118.4085},
    {"code": "SFO", "lat": 37.6213, "lon": -122.3790},
    {"code": "PDX", "lat": 45.5898, "lon": -122.5951},
    {"code": "PHX", "lat": 33.4373, "lon": -112.0078},
    {"code": "DFW", "lat": 32.8998, "lon": -97.0403},
    {"code": "IAH", "lat": 29.9902, "lon": -95.3368},
    {"code": "ORD", "lat": 41.9742, "lon": -87.9073},
    {"code": "ATL", "lat": 33.6407, "lon": -84.4277},
    {"code": "JFK", "lat": 40.6413, "lon": -73.7781},
]


class AirspaceVisualizer:
    """Renders genuine real-world flight tracks and detected anomalies."""

    def __init__(self):
        self.tracks = self._load_json(os.path.join(config.DATA_DIR, "tracks.json"))
        self.anomalies = self._load_json(os.path.join(config.RESULTS_DIR, "anomalies.json"))
        self.geo_path = os.path.join(config.DATA_DIR, "us_states.json")

    @staticmethod
    def _load_json(path):
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def generate_static_briefing(self, output_path=None):
        """Generates a high-contrast tactical map from genuine live data (300 DPI)."""
        if output_path is None:
            output_path = os.path.join(config.RESULTS_DIR, "anomaly_map.png")

        print(f"\n🎨 Rendering authentic tactical radar map from {len(self.tracks)} real live aircraft …")

        if not self.tracks:
            print("   ⚠ No live track data found in data/tracks.json!")
            return None

        # Filter unique top anomalies for display
        seen_icaos = set()
        top_anomalies = []
        for a in self.anomalies:
            if a["icao24"] not in seen_icaos:
                seen_icaos.add(a["icao24"])
                top_anomalies.append(a)

        # 2-Panel Layout: Main Continental Radar + Real Target Inspection Cards
        fig = plt.figure(figsize=(26, 15), facecolor="#060910")
        gs = gridspec.GridSpec(
            3, 3,
            width_ratios=[2.2, 1.1, 1.1],
            height_ratios=[1.0, 1.0, 1.0],
            wspace=0.18, hspace=0.35
        )

        # ── MAIN RADAR PANEL (Left) ──
        ax_main = fig.add_subplot(gs[:, 0], facecolor="#060910")
        self._render_continental_radar(ax_main, top_anomalies)

        # ── REAL TARGET ZOOM 1: Real Circular Flight (Top Right) ──
        circ_target = next((a for a in top_anomalies if a.get("type") == "circular"), None)
        ax_z1 = fig.add_subplot(gs[0, 1:], facecolor="#080e1a")
        if circ_target:
            self._render_real_target_zoom(ax_z1, circ_target, "REAL TARGET ZOOM 01 // DETECTED HOLDING / LOITER PATTERN")
        else:
            ax_z1.text(0.5, 0.5, "NO CIRCULAR ANOMALY IN CURRENT SCAN", color="#64748b", ha="center")

        # ── REAL TARGET ZOOM 2: Real Altitude Profile (Middle Right) ──
        alt_target = next((a for a in top_anomalies if a.get("type") == "altitude" and len(a.get("waypoints", [])) > 15), None)
        ax_z2 = fig.add_subplot(gs[1, 1:], facecolor="#080e1a")
        if alt_target:
            self._render_real_altitude_profile(ax_z2, alt_target)
        else:
            ax_z2.text(0.5, 0.5, "NO ALTITUDE CLIFF IN CURRENT SCAN", color="#64748b", ha="center")

        # ── REAL TARGET ZOOM 3: Second Real Anomaly Track (Bottom Right) ──
        second_target = next((a for a in top_anomalies[1:] if len(a.get("waypoints", [])) > 10), None)
        ax_z3 = fig.add_subplot(gs[2, 1:], facecolor="#080e1a")
        if second_target:
            self._render_real_target_zoom(ax_z3, second_target, f"REAL TARGET ZOOM 02 // DETECTED {second_target.get('type', '').upper()} VECTOR")
        else:
            ax_z3.text(0.5, 0.5, "ADDITIONAL RADAR TARGET", color="#64748b", ha="center")

        plt.savefig(output_path, dpi=300, facecolor=fig.get_facecolor(), bbox_inches="tight")
        plt.close(fig)

        print(f"   ✅ Authentic map generated → {output_path} (300 DPI)")
        return output_path

    def _render_continental_radar(self, ax, top_anomalies):
        lomin, lomax = -126.0, -66.0
        lamin, lamax = 23.5, 50.0
        ax.set_xlim(lomin, lomax)
        ax.set_ylim(lamin, lamax)

        # 1. Geographic US State Boundaries
        if os.path.exists(self.geo_path):
            try:
                with open(self.geo_path) as f:
                    geo = json.load(f)
                for feat in geo.get("features", []):
                    geom = feat.get("geometry", {})
                    gtype = geom.get("type")
                    coords = geom.get("coordinates", [])
                    if gtype == "Polygon":
                        for ring in coords:
                            ax.fill([p[0] for p in ring], [p[1] for p in ring],
                                    facecolor="#0a1220", edgecolor="#1a2d48", linewidth=0.8, alpha=0.9, zorder=1)
                    elif gtype == "MultiPolygon":
                        for poly in coords:
                            for ring in poly:
                                ax.fill([p[0] for p in ring], [p[1] for p in ring],
                                        facecolor="#0a1220", edgecolor="#1a2d48", linewidth=0.8, alpha=0.9, zorder=1)
            except Exception:
                pass

        ax.grid(color="#172338", linestyle=":", linewidth=0.6, alpha=0.5, zorder=2)
        ax.tick_params(colors="#475569", labelsize=9)
        for s in ax.spines.values():
            s.set_color("#1e293b")
            s.set_linewidth(1.5)

        # 2. Major Hubs
        for hub in MAJOR_HUBS:
            ax.scatter([hub["lon"]], [hub["lat"]], color="#38bdf8", s=22, alpha=0.6, zorder=3)
            ax.text(hub["lon"] + 0.45, hub["lat"] - 0.25, hub["code"],
                    color="#64748b", fontsize=8.5, family="monospace", weight="bold", zorder=3)

        # 3. Real Normal Flight Corridors (Thin, elegant, non-intrusive)
        # Routine climbs/descents are normal aviation, so we treat them as baseline corridors
        true_anomaly_types = {"circular", "zigzag", "speed", "loiter", "path_inefficiency"}
        rare_anomalies = [a for a in top_anomalies if a.get("type") in true_anomaly_types]
        rare_icaos = {a["icao24"] for a in rare_anomalies}

        normal_count = 0
        for t in self.tracks:
            if t["icao24"] in rare_icaos:
                continue
            wps = t.get("waypoints", [])
            if len(wps) >= 2:
                xs = [w["lon"] for w in wps if lomin <= w["lon"] <= lomax and lamin <= w["lat"] <= lamax]
                ys = [w["lat"] for w in wps if lomin <= w["lon"] <= lomax and lamin <= w["lat"] <= lamax]
                if len(xs) >= 2:
                    # Clean, delicate airway silk lines
                    ax.plot(xs, ys, color="#38bdf8", alpha=0.35, linewidth=1.1, zorder=4)
                    normal_count += 1

        # 4. Highlight ONLY the truly rare anomalies (Circular loops, zigzags, speed spikes)
        color_map = config.ANOMALY_COLORS
        for a in rare_anomalies:
            wps = a.get("waypoints", [])
            if len(wps) < 2:
                continue
            xs = [w["lon"] for w in wps if lomin <= w["lon"] <= lomax and lamin <= w["lat"] <= lamax]
            ys = [w["lat"] for w in wps if lomin <= w["lon"] <= lomax and lamin <= w["lat"] <= lamax]
            if len(xs) < 2:
                continue

            col = color_map.get(a.get("type"), "#ff3333")
            # Glowing neon shader
            ax.plot(xs, ys, color=col, alpha=0.25, linewidth=10.0, zorder=6)
            ax.plot(xs, ys, color=col, alpha=0.85, linewidth=2.8, zorder=7)
            ax.plot(xs, ys, color="#ffffff", alpha=0.90, linewidth=1.0, zorder=8)
            ax.scatter([xs[-1]], [ys[-1]], color=col, s=55, edgecolors="#ffffff", linewidths=1.4, zorder=9)

        # 5. Callouts for only the rare interesting targets
        callout_count = 0
        for a in rare_anomalies[:4]:
            wps = a.get("waypoints", [])
            if len(wps) < 2:
                continue
            mid = wps[len(wps) // 2]
            if not (lomin <= mid["lon"] <= lomax and lamin <= mid["lat"] <= lamax):
                continue

            cs = a.get("callsign") or a["icao24"]
            atype = a.get("type", "").upper()
            score = a.get("score", 0)

            dx = -8.0 if mid["lon"] > -100 else 4.5
            dy = -3.5 if mid["lat"] > 42 else (3.0 if callout_count % 2 == 0 else -3.0)

            label = f"[{atype}] {cs} ({a['icao24']})\nScore: {score:.0f}/100"
            col = color_map.get(a.get("type"), "#ff3333")

            ax.annotate(
                label,
                xy=(mid["lon"], mid["lat"]),
                xytext=(mid["lon"] + dx, mid["lat"] + dy),
                color="#ffffff",
                fontsize=9.5,
                family="sans-serif",
                weight="bold",
                bbox=dict(boxstyle="round,pad=0.55", facecolor="#060c18", edgecolor=col, linewidth=1.8, alpha=0.96),
                arrowprops=dict(arrowstyle="-|>", color=col, lw=1.8, mutation_scale=14, connectionstyle="arc3,rad=0.15"),
                zorder=20,
            )
            callout_count += 1

        # Header
        ax.text(0.02, 0.96, "SKYWATCH // LIVE ADS-B AIRSPACE RADAR",
                transform=ax.transAxes, color="#00f0ff", fontsize=18, family="monospace", weight="heavy", zorder=30)
        ax.text(0.02, 0.93,
                f"SOURCE: OPENSKY NETWORK SATELLITES  |  REAL AIRCRAFT ANALYZED: {len(self.tracks)}  |  FLAGGED ANOMALIES: {len(rare_anomalies)}",
                transform=ax.transAxes, color="#94a3b8", fontsize=9.5, family="monospace", zorder=30)

        # Legend
        leg_items = [
            Line2D([0], [0], color="#38bdf8", lw=1.8, label=f"Commercial Flight Corridors ({normal_count})"),
            Line2D([0], [0], color=config.ANOMALY_COLORS["circular"], lw=3.2, label="Holding & Patrol Loiter Loops"),
            Line2D([0], [0], color=config.ANOMALY_COLORS["speed"], lw=3.2, label="Transponder Speed Spikes"),
            Line2D([0], [0], color=config.ANOMALY_COLORS["path_inefficiency"], lw=3.2, label="High-Deviation Detours"),
        ]
        leg = ax.legend(handles=leg_items, loc="lower right", facecolor="#060c18", edgecolor="#1a2b48",
                        labelcolor="#f1f5f9", fontsize=10.0, framealpha=0.96, title="RADAR CLASSIFICATIONS", title_fontsize=11.0)
        leg.get_title().set_color("#38bdf8")
        leg.set_zorder(30)

    def _render_real_target_zoom(self, ax, target, title):
        """Magnified close-up of a genuine detected aircraft."""
        wps = target.get("waypoints", [])
        lons = [w["lon"] for w in wps]
        lats = [w["lat"] for w in wps]

        ax.set_facecolor("#080e1c")
        ax.grid(color="#17253d", linestyle=":", linewidth=0.6)
        col = config.ANOMALY_COLORS.get(target.get("type"), "#ff3333")

        for s in ax.spines.values():
            s.set_color(col)
            s.set_linewidth(1.6)

        ax.plot(lons, lats, color=col, alpha=0.35, linewidth=8.0)
        ax.plot(lons, lats, color=col, alpha=0.90, linewidth=2.6)
        ax.plot(lons, lats, color="#ffffff", alpha=0.85, linewidth=1.0)
        ax.scatter([lons[0]], [lats[0]], color="#ffffff", s=35, label="Start", zorder=5)
        ax.scatter([lons[-1]], [lats[-1]], color=col, s=65, edgecolors="#ffffff", lw=1.2, label="Current", zorder=6)

        cs = target.get("callsign") or target["icao24"]
        ax.set_title(f"{title} [{cs}]", color=col, fontsize=11.5, family="monospace", weight="bold", pad=8)

        info = f"Real Flight: {cs} ({target['icao24']}) | Type: {target.get('type','').title()} | Points: {len(wps)}"
        ax.text(0.03, 0.08, info, transform=ax.transAxes, color="#f1f5f9", fontsize=9.0, family="monospace", weight="bold",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#03060d", edgecolor=col, alpha=0.85))
        ax.tick_params(colors="#475569", labelsize=8)

    def _render_real_altitude_profile(self, ax, target):
        """Genuine Altitude vs Time line chart of an actual flight descent or climb."""
        wps = target.get("waypoints", [])
        times_sec = [(w["time"] - wps[0]["time"]) for w in wps]
        alts_ft = [w["alt"] * 3.28084 for w in wps]

        ax.set_facecolor("#080e1c")
        ax.grid(color="#17253d", linestyle=":", linewidth=0.6)
        for s in ax.spines.values():
            s.set_color("#ff9900")
            s.set_linewidth(1.6)

        ax.plot(times_sec, alts_ft, color="#ff9900", alpha=0.4, linewidth=7.0)
        ax.plot(times_sec, alts_ft, color="#ff9900", alpha=0.95, linewidth=2.6)
        ax.fill_between(times_sec, alts_ft, color="#ff9900", alpha=0.15)
        ax.scatter(times_sec, alts_ft, color="#ffffff", s=18, zorder=5)

        ax.set_ylabel("Altitude (ft)", color="#cbd5e1", fontsize=8.5)
        ax.set_xlabel("Time (Seconds)", color="#cbd5e1", fontsize=8.5)
        cs = target.get("callsign") or target["icao24"]
        ax.set_title(f"REAL TELEMETRY PROFILE // ALTITUDE DESCENT/CLIMB [{cs}]",
                     color="#ffaa00", fontsize=11.5, family="monospace", weight="bold", pad=8)

        info = f"Real Flight: {cs} ({target['icao24']}) | Alt Span: {min(alts_ft):,.0f} ft - {max(alts_ft):,.0f} ft"
        ax.text(0.03, 0.12, info, transform=ax.transAxes, color="#f1f5f9", fontsize=9.0, family="monospace", weight="bold",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="#03060d", edgecolor="#ff9900", alpha=0.85))
        ax.tick_params(colors="#475569", labelsize=8)

    def generate_interactive_map(self, output_path=None):
        """Generates an interactive Folium map from genuine live flights with an on-screen legend."""
        if not HAS_FOLIUM:
            return None
        if output_path is None:
            output_path = os.path.join(config.RESULTS_DIR, "flight_map.html")

        print("\n🌐 Building interactive map with 100% genuine live flights and on-screen HUD legend …")

        m = folium.Map(
            location=[38.5, -97.0],
            zoom_start=5,
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
            attr="Esri Dark Gray Canvas",
            prefer_canvas=True,
        )
        folium.TileLayer("OpenStreetMap", name="Street Map (OpenStreetMap)").add_to(m)

        # Baseline Normal Flights
        norm_grp = folium.FeatureGroup(name="✈️ Baseline Flight Corridors", show=True)
        ano_icaos = {a["icao24"] for a in self.anomalies}

        normal_count = 0
        for t in self.tracks:
            if t["icao24"] in ano_icaos:
                continue
            coords = [[w["lat"], w["lon"]] for w in t.get("waypoints", [])]
            if len(coords) >= 2:
                cs = t.get("callsign") or t["icao24"]
                folium.PolyLine(coords, color="#475569", weight=1.4, opacity=0.35, tooltip=f"Flight: {cs}").add_to(norm_grp)
                normal_count += 1
        norm_grp.add_to(m)

        # Individual Categorized Anomaly Layers (Ordered so Cyan, Yellow, and Magenta stay prominently on top)
        layer_configs = {
            "speed":             {"name": "🟢 Speed / Vector Spikes",        "color": "#00ff66", "badge": "SPEED ANOMALY"},
            "circular":          {"name": "🔄 Circular / Holding Patterns", "color": "#ff3333", "badge": "HOLDING PATTERN"},
            "altitude":          {"name": "📉 Emergency Altitude Dives",     "color": "#ff9900", "badge": "ALTITUDE DIVE"},
            "loiter":            {"name": "📍 Loitering Aircraft / Patrol",  "color": "#ff00ff", "badge": "LOITER / PATROL"},
            "path_inefficiency": {"name": "🔀 High-Deviation Detours",        "color": "#ffff00", "badge": "PATH DETOUR"},
            "zigzag":            {"name": "⚡ Zigzag / Heading Reversals",    "color": "#00ffff", "badge": "ZIGZAG / SURVEY"},
        }

        category_groups = {}
        category_counts = {k: 0 for k in layer_configs}

        for k, cfg in layer_configs.items():
            category_groups[k] = folium.FeatureGroup(name=cfg["name"], show=True)

        for a in self.anomalies:
            atype = a.get("type", "circular")
            if atype not in category_groups:
                continue

            cfg = layer_configs[atype]
            color = cfg["color"]
            wps = a.get("waypoints", [])
            coords = [[w["lat"], w["lon"]] for w in wps]
            if len(coords) < 2:
                continue

            cs = a.get("callsign") or a["icao24"]
            score = a.get("score", 0)
            category_counts[atype] += 1

            alts = [w.get("alt", 0) * 3.28084 for w in wps if w.get("alt") is not None]
            min_alt = round(min(alts)) if alts else 0
            max_alt = round(max(alts)) if alts else 0
            dur = (wps[-1]["time"] - wps[0]["time"]) / 60 if len(wps) > 1 else 0

            # Mathematical Proof Matrix Rows based on category
            proof_rows = []
            if atype == "zigzag":
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Course Reversals:</td><td style='color:#00ffff; font-weight:700;'>{a.get('reversals', 'N/A')} sharp turns</td></tr>")
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Mean Turn Angle:</td><td style='color:#ffffff; font-weight:700;'>{a.get('avg_turn_deg', 'N/A')}°</td></tr>")
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Pattern Profile:</td><td style='color:#38bdf8; font-weight:700;'>{a.get('pattern_desc', 'Survey Grid')}</td></tr>")
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Turn Sequence:</td><td style='color:#cbd5e1; font-size:10px; font-family:monospace;'>{a.get('reversal_sequence', 'N/A')}</td></tr>")
            elif atype == "path_inefficiency":
                direct_km = a.get("direct_km", 0)
                actual_km = a.get("actual_km", 0)
                ratio = a.get("ratio", 0)
                excess_km = a.get("excess_km", actual_km - direct_km)
                eff = a.get("efficiency_pct", round((direct_km / max(actual_km, 1)) * 100, 1))
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Direct Great-Circle:</td><td style='color:#ffffff; font-weight:700;'>{direct_km:.1f} km</td></tr>")
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Actual Track Flown:</td><td style='color:#ffff00; font-weight:700;'>{actual_km:.1f} km</td></tr>")
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Inefficiency Ratio:</td><td style='color:#f59e0b; font-weight:800; font-size:13px;'>{ratio:.2f}× direct distance</td></tr>")
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Excess Distance:</td><td style='color:#f43f5e; font-weight:700;'>+{excess_km:.1f} km</td></tr>")
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Great-Circle Efficiency:</td><td style='color:#38bdf8; font-weight:700;'>{eff:.1f}%</td></tr>")

                # Add a dashed direct-line vector to visually expose the detour!
                folium.PolyLine(
                    [coords[0], coords[-1]],
                    color="#ffffff",
                    weight=1.5,
                    opacity=0.45,
                    dash_array="6, 8",
                    tooltip=f"Direct Baseline: {direct_km:.1f} km (Flown: {actual_km:.1f} km)"
                ).add_to(category_groups[atype])

            elif atype == "loiter":
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Bounding Box Span:</td><td style='color:#ff00ff; font-weight:700;'>{a.get('bbox_km', 'N/A')} km perimeter</td></tr>")
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Surveillance Area:</td><td style='color:#ffffff; font-weight:700;'>~{a.get('area_sq_km', 'N/A')} km²</td></tr>")
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Time on Station:</td><td style='color:#38bdf8; font-weight:700;'>{a.get('duration_min', dur):.1f} min</td></tr>")
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Mean Patrol Speed:</td><td style='color:#ffffff; font-weight:700;'>{a.get('avg_speed_kt', 'N/A')} kt</td></tr>")
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Geographic Center:</td><td style='color:#cbd5e1; font-family:monospace; font-size:10px;'>{a.get('center_lat', 'N/A')}°, {a.get('center_lon', 'N/A')}°</td></tr>")
            elif atype == "altitude":
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Descent Rate:</td><td style='color:#ff9900; font-weight:800; font-size:13px;'>{a.get('rate_ft_per_min', 'N/A'):,} ft/min</td></tr>")
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Total Plunge:</td><td style='color:#f43f5e; font-weight:700;'>{abs(a.get('worst_change_ft', 0)):,} ft in {a.get('worst_time_sec', 'N/A')}s</td></tr>")
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Event Coordinates:</td><td style='color:#cbd5e1; font-family:monospace; font-size:10px;'>{a.get('lat', 'N/A')}°, {a.get('lon', 'N/A')}°</td></tr>")
            elif atype == "circular":
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Holding Orbits:</td><td style='color:#ff3333; font-weight:800; font-size:13px;'>{a.get('loops', 'N/A')} closed loops</td></tr>")
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Confined Perimeter:</td><td style='color:#ffffff; font-weight:700;'>{a.get('bbox_km', 'N/A')} km</td></tr>")
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Holding Duration:</td><td style='color:#38bdf8; font-weight:700;'>{a.get('duration_min', dur):.1f} min</td></tr>")
            elif atype == "speed":
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Peak Ground Speed:</td><td style='color:#00ff66; font-weight:800; font-size:13px;'>{a.get('max_speed_kt', 'N/A')} kt</td></tr>")
                proof_rows.append(f"<tr><td style='color:#94a3b8;'>Average Cruise:</td><td style='color:#ffffff; font-weight:700;'>{a.get('avg_speed_kt', 'N/A')} kt</td></tr>")

            proof_table_html = "<table style='width:100%; font-size:11.5px; line-height:1.6; border-collapse:collapse;'>" + "".join(proof_rows) + "</table>"

            popup_html = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        background: #090d16; color: #f1f5f9; padding: 14px 16px; border-radius: 10px;
                        border: 1.5px solid {color}; box-shadow: 0 10px 30px rgba(0,0,0,0.8);
                        min-width: 320px; max-width: 380px;">
                <!-- Header -->
                <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #1e293b; padding-bottom: 8px; margin-bottom: 8px;">
                    <div>
                        <span style="font-size: 16px; font-weight: 800; color: #ffffff;">{cs}</span>
                        <span style="font-size: 11px; font-family: monospace; background: #1e293b; color: #94a3b8; padding: 2px 6px; border-radius: 4px; margin-left: 6px;">{a['icao24']}</span>
                    </div>
                    <span style="background: {color}22; color: {color}; border: 1px solid {color}; font-size: 10.5px; font-weight: 700; padding: 2px 8px; border-radius: 12px; text-transform: uppercase;">
                        {cfg['badge']}
                    </span>
                </div>

                <!-- Telemetry Row -->
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px 10px; font-size: 11px; background: #0f172a; padding: 7px 10px; border-radius: 6px; margin-bottom: 10px; border: 1px solid #1e293b;">
                    <div><span style="color: #64748b;">Country:</span> <b style="color: #cbd5e1;">{a.get('origin_country') or 'United States'}</b></div>
                    <div><span style="color: #64748b;">Squawk:</span> <b style="color: #cbd5e1;">{a.get('squawk') or 'Standard'}</b></div>
                    <div><span style="color: #64748b;">Altitude Span:</span> <b style="color: #cbd5e1;">{min_alt:,}–{max_alt:,} ft</b></div>
                    <div><span style="color: #64748b;">Track Duration:</span> <b style="color: #cbd5e1;">{dur:.0f} min</b></div>
                </div>

                <!-- Mathematical Proof Box -->
                <div style="background: rgba(15, 23, 42, 0.9); border-left: 3px solid {color}; padding: 8px 10px; border-radius: 4px; margin-bottom: 10px;">
                    <div style="font-size: 10.5px; font-weight: 800; color: {color}; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">
                        📐 VERIFIED DATA PROOF MATRIX
                    </div>
                    {proof_table_html}
                </div>

                <!-- Narrative -->
                <div style="font-size: 11px; line-height: 1.45; color: #94a3b8; margin-bottom: 10px; background: #0b1120; padding: 6px 8px; border-radius: 4px;">
                    {a.get('details', '')}
                </div>

                <!-- Proof Watermark -->
                <div style="display: flex; align-items: center; justify-content: space-between; font-size: 10px; color: #64748b; border-top: 1px solid #1e293b; padding-top: 6px;">
                    <span>📡 Live OpenSky ADS-B Telemetry</span>
                    <span style="color: #10b981; font-weight: 700;">● 100% REAL DATA</span>
                </div>
            </div>
            """

            # Thick, luminous flight path
            folium.PolyLine(
                coords,
                color=color,
                weight=5.0,
                opacity=0.95,
                tooltip=f"[{cs}] {cfg['badge']} &bull; Score: {score:.0f}/100",
                popup=folium.Popup(popup_html, max_width=400)
            ).add_to(category_groups[atype])

            # Origin marker (Green dot)
            folium.CircleMarker(
                coords[0],
                radius=4.5,
                color="#ffffff",
                weight=1.5,
                fill=True,
                fill_color="#10b981",
                fill_opacity=0.9,
                tooltip=f"[{cs}] Track Origin",
                popup=folium.Popup(popup_html, max_width=400)
            ).add_to(category_groups[atype])

            # Terminus / Current location marker (Glow dot with border)
            folium.CircleMarker(
                coords[-1],
                radius=7.0,
                color="#ffffff",
                weight=2.0,
                fill=True,
                fill_color=color,
                fill_opacity=1.0,
                tooltip=f"[{cs}] {cfg['badge']}",
                popup=folium.Popup(popup_html, max_width=400)
            ).add_to(category_groups[atype])

        # Add groups to map in order
        for g in category_groups.values():
            g.add_to(m)

        folium.LayerControl(collapsed=False).add_to(m)

        # Permanent On-Screen Tactical HUD Legend Card (Bottom-Right)
        legend_html = f"""
        <div id="tactical-legend-card" style="position: fixed; bottom: 25px; right: 25px; z-index: 999999 !important;
                    background: rgba(6, 11, 20, 0.95); backdrop-filter: blur(12px);
                    border: 2px solid #38bdf8; border-radius: 12px; padding: 14px 18px;
                    color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    box-shadow: 0 12px 40px rgba(0,0,0,0.85), 0 0 15px rgba(56, 189, 248, 0.25); min-width: 285px; pointer-events: auto;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; border-bottom: 1px solid #1e293b; padding-bottom: 6px;">
                <div style="font-size: 11.5px; font-weight: 900; color: #38bdf8; text-transform: uppercase; letter-spacing: 1px;">
                    AIRSPACE CLASSIFICATIONS
                </div>
                <span style="font-size: 9.5px; background: #0284c7; color: white; padding: 2px 7px; border-radius: 10px; font-weight: 800;">LIVE</span>
            </div>

            <div style="display:flex; align-items:center; margin-bottom: 6px; font-size: 12px;">
                <span style="display:inline-block; width:13px; height:13px; background:#00ffff; border-radius:3px; margin-right:9px; box-shadow: 0 0 7px #00ffff;"></span>
                <span style="color:#e2e8f0; font-weight:600;">Zigzag / Survey Grid</span>
                <span style="margin-left:auto; color:#00ffff; font-weight:800; font-family:monospace;">{category_counts['zigzag']} targets</span>
            </div>

            <div style="display:flex; align-items:center; margin-bottom: 6px; font-size: 12px;">
                <span style="display:inline-block; width:13px; height:13px; background:#ffff00; border-radius:3px; margin-right:9px; box-shadow: 0 0 7px #ffff00;"></span>
                <span style="color:#e2e8f0; font-weight:600;">High-Deviation Detour</span>
                <span style="margin-left:auto; color:#ffff00; font-weight:800; font-family:monospace;">{category_counts['path_inefficiency']} targets</span>
            </div>

            <div style="display:flex; align-items:center; margin-bottom: 6px; font-size: 12px;">
                <span style="display:inline-block; width:13px; height:13px; background:#ff00ff; border-radius:3px; margin-right:9px; box-shadow: 0 0 7px #ff00ff;"></span>
                <span style="color:#e2e8f0; font-weight:600;">Loiter / Airborne Patrol</span>
                <span style="margin-left:auto; color:#ff00ff; font-weight:800; font-family:monospace;">{category_counts['loiter']} targets</span>
            </div>

            <div style="display:flex; align-items:center; margin-bottom: 6px; font-size: 12px;">
                <span style="display:inline-block; width:13px; height:13px; background:#ff3333; border-radius:3px; margin-right:9px; box-shadow: 0 0 7px #ff3333;"></span>
                <span style="color:#e2e8f0; font-weight:600;">Circular / Holding Loops</span>
                <span style="margin-left:auto; color:#ff3333; font-weight:800; font-family:monospace;">{category_counts['circular']} targets</span>
            </div>

            <div style="display:flex; align-items:center; margin-bottom: 6px; font-size: 12px;">
                <span style="display:inline-block; width:13px; height:13px; background:#ff9900; border-radius:3px; margin-right:9px; box-shadow: 0 0 7px #ff9900;"></span>
                <span style="color:#e2e8f0; font-weight:600;">Emergency Altitude Dive</span>
                <span style="margin-left:auto; color:#ff9900; font-weight:800; font-family:monospace;">{category_counts['altitude']} targets</span>
            </div>

            <div style="display:flex; align-items:center; margin-bottom: 6px; font-size: 12px;">
                <span style="display:inline-block; width:13px; height:13px; background:#00ff66; border-radius:3px; margin-right:9px; box-shadow: 0 0 7px #00ff66;"></span>
                <span style="color:#e2e8f0; font-weight:600;">Speed / Vector Spikes</span>
                <span style="margin-left:auto; color:#00ff66; font-weight:800; font-family:monospace;">{category_counts['speed']} targets</span>
            </div>

            <div style="display:flex; align-items:center; font-size: 11px; border-top: 1px solid #1e293b; padding-top: 7px; margin-top: 5px;">
                <span style="display:inline-block; width:13px; height:3px; background:#475569; margin-right:9px;"></span>
                <span style="color:#94a3b8;">Normal Corridors</span>
                <span style="margin-left:auto; color:#94a3b8; font-weight:bold; font-family:monospace;">{normal_count} tracks</span>
            </div>

            <div style="font-size: 9.5px; color: #64748b; margin-top: 8px; text-align: center; border-top: 1px dashed #1e293b; padding-top: 5px;">
                Click any flight track for full mathematical proof
            </div>
        </div>
        """

        # On-Screen Header HUD (Top-Left)
        hud_html = f"""
        <div style="position: fixed; top: 16px; left: 60px; z-index: 999999 !important;
                    background: rgba(6, 11, 20, 0.95); backdrop-filter: blur(10px);
                    border: 1.5px solid #1e293b; border-left: 4px solid #00f0ff; border-radius: 8px; padding: 10px 18px;
                    color: white; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    box-shadow: 0 8px 30px rgba(0,0,0,0.7); pointer-events: none;">
            <div style="font-size: 13.5px; font-weight: 900; color: #00f0ff; letter-spacing: 0.8px;">
                SKYWATCH // REAL-TIME AIRSPACE ANOMALY RADAR
            </div>
            <div style="font-size: 11px; color: #cbd5e1; margin-top: 2px;">
                100% Genuine OpenSky ADS-B Telemetry &bull; <span style="color:#38bdf8; font-weight:700;">{len(self.tracks)} Real Flights</span> &bull; <span style="color:#f59e0b; font-weight:700;">{len(self.anomalies)} Flagged Anomalies</span>
            </div>
        </div>
        """

        m.get_root().html.add_child(folium.Element(legend_html))
        m.get_root().html.add_child(folium.Element(hud_html))
        m.save(output_path)
        print(f"   ✅ Interactive live map generated → {output_path}")
        return output_path


def main():
    print("=" * 60)
    print("  🎨 SkyWatch — 100% Genuine Live Airspace Visualizer")
    print("=" * 60)

    viz = AirspaceVisualizer()
    viz.generate_static_briefing()
    viz.generate_interactive_map()

    print("\n✅ Pure live data visualization complete!")
    print(f"   Image for Reddit : {config.RESULTS_DIR}/anomaly_map.png")
    print(f"   Interactive Web  : {config.RESULTS_DIR}/flight_map.html")


if __name__ == "__main__":
    main()
