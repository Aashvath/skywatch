# 🛰️ SkyWatch — Autonomous ADS-B Flight Anomaly Detection Engine

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Telemetry: OpenSky Network](https://img.shields.io/badge/Data-OpenSky%20ADS--B-orange.svg)](https://opensky-network.org/)
[![Built with Claude](https://img.shields.io/badge/Built%20with-Claude-6366f1.svg)](https://claude.ai)

> **"I fed 50,000 live flight trajectories into an anomaly detection algorithm I wrote with Claude. Here are the unexplained patterns I found."**

**SkyWatch** is an open-source flight telemetry analysis engine designed to ingest thousands of real-time ADS-B transponder broadcasts, trace multi-dimensional trajectory corridors, and algorithmically isolate statistical anomalies—including military holding patterns, rapid tactical descents, drone survey grids, and unauthorized maritime loitering.

---

## 🗺️ Visual Radar Output

![SkyWatch Airspace Anomaly Radar](data/results/anomaly_map.png)

*All normal commercial corridors rendered in baseline slate gray. Anomalies isolated and rendered with high-contrast tactical HUD vectors.*

---

## ⚡ The 7 Anomaly Detection Algorithms

SkyWatch processes each flight trajectory through seven independent mathematical heuristics:

| # | Detector | Color Code | What It Isolates | Heuristic Logic |
|---|---|---|---|---|
| 1 | **Circular / Holding Loops** | Red (`#ff3333`) | Holding stacks, VIP staging, reconnaissance | Evaluates spatial return frequency within geographically confined perimeter: loops $\ge 2$, return distance $\le 12\text{ km}$, $\Delta t \ge 120\text{s}$, and bounding box $\le 60\text{ km}$. |
| 2 | **Emergency Altitude Dives** | Orange (`#ff9900`) | Rapid descents, emergency drops, cabin depressurization | Strict vertical rate plunge detector: flags descents $\ge 3,500\text{ ft in } \le 90\text{s}$ at $\ge 3,500\text{ ft/min}$ (filters out routine takeoff climbs). |
| 3 | **Airborne Loitering / Patrol** | Magenta (`#ff00ff`) | Police/medical helicopters, surveillance, border patrol | Calibrated perimeter containment: bounding box diagonal $D \le 45\text{ km}$ across airborne duration $T \ge 5.0\text{ min}$ with geographic center calculation. |
| 4 | **Zigzag / Survey Grids** | Cyan (`#00ffff`) | Precision LIDAR grids, photogrammetry, law enforcement search | Aeronautical flight-leg segmentation ($\ge 0.8\text{ km}$ or $\Delta t \ge 30\text{s}$): isolates sharp heading reversals $\Delta \theta \ge 70^\circ$ (identifying reciprocal swath lines). |
| 5 | **High-Deviation Detours** | Yellow (`#ffff00`) | Severe ATC route diversions, holding delays, area scans | Computes ratio of cumulative path distance against great-circle Haversine displacement: $\text{Ratio} \ge 1.50\times$, rendering dashed direct comparison vectors. |
| 6 | **Speed / Vector Spikes** | Green (`#00ff66`) | Mach-speed anomalies, sensor telemetry jumps | Ground speed derived from ADS-B coordinate differentials: flags speeds $> 680\text{ kt}$ or sustained anomalous vector spikes. |
| 7 | **Sustained Low-Altitude Flight** | Deep Orange (`#ff6600`) | Low-level terrain flights, pipeline inspections | Excludes takeoff/landing phases; flags sustained cruising $< 800\text{ ft AGL}$ for $> 5\text{ minutes}$. |

---

## 🚀 Quickstart

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/Aashvath/skywatch.git
cd skywatch
pip install -r requirements.txt
```

### 2. Configure Credentials (Optional)
Register for free at [OpenSky Network](https://opensky-network.org/) for higher API rate limits.  
Edit `config.py` with your username:
```python
OPENSKY_USERNAME = "aashvathgupta"
OPENSKY_PASSWORD = "your_password"
```
*(SkyWatch also operates in anonymous mode out of the box).*

### 3. Run the Pure Live Telemetry Pipeline

```bash
# Step 1: Ingest live flight state vectors & trajectory waypoints from OpenSky
python collect_data.py

# Step 2: Execute the 7 anomaly detection algorithms with mathematical proof
python detect_anomalies.py

# Step 3: Render publication-quality maps (Static 300 DPI Radar + Interactive Folium Web)
python visualize.py
```

---

## 📁 Repository Structure

```
skywatch/
├── config.py             # Global bounding boxes, thresholds, colors, and API credentials
├── collect_data.py       # OpenSky ADS-B REST harvester with auto-retry and checkpoints
├── detect_anomalies.py   # 7 mathematical detection algorithms & severity scoring
├── visualize.py          # Dual rendering engine (300 DPI static HUD map + Folium HTML)
├── requirements.txt      # Python dependencies
└── data/
    ├── tracks.json       # Ingested flight trajectories
    └── results/
        ├── anomaly_map.png       # 300 DPI tactical HUD image (for Reddit/Twitter)
        ├── flight_map.html       # Interactive web map with clickable telemetry
        ├── anomalies_summary.json# Clean JSON export of flagged targets
        └── report.txt            # Human-readable incident briefing
```

---

## 🔬 How This Was Built

This entire pipeline was architected, coded, and debugged using **Claude** by Anthropic. 

The algorithmic prompts, XML constraint frameworks, and prompt-chaining techniques used to design SkyWatch's mathematical heuristics are documented in:

📘 **[Mastering Claude: The Practical Playbook for High-Output Work, Coding, and Automation](https://www.amazon.com/dp/B0DJ7W7XYZ)**  
*Under 100 pages • No academic fluff • Production agentic workflows, CLI mastery, and 100+ MCP integration maps.*

---

## ⚖️ License & Attribution
Distributed under the **MIT License**. Flight telemetry data provided via the [OpenSky Network](https://opensky-network.org/) open API.
