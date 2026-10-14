"""
SkyWatch Configuration
=====================
All configurable parameters for the flight anomaly detection pipeline.
Edit this file to change regions, thresholds, and credentials.
"""

# ============================================================
# OpenSky Network Credentials
# Register free at https://opensky-network.org/register
# NOTE: Use your OpenSky USERNAME (not email) below.
# ============================================================
OPENSKY_USERNAME = "aashvathgupta"   # OpenSky username
OPENSKY_PASSWORD = ""                # Enter your OpenSky password here if needed

# ============================================================
# Region Presets — Pick your hunting ground
# ============================================================
REGIONS = {
    "usa": {
        "name": "Continental USA",
        "lamin": 24.396308,
        "lamax": 49.384358,
        "lomin": -125.0,
        "lomax": -66.93457,
        "center": [39.8283, -98.5795],
        "zoom": 4,
    },
    "europe": {
        "name": "Western Europe",
        "lamin": 36.0,
        "lamax": 60.0,
        "lomin": -10.0,
        "lomax": 30.0,
        "center": [48.0, 10.0],
        "zoom": 4,
    },
    "nevada": {
        "name": "Nevada / Area 51 Region",
        "lamin": 35.0,
        "lamax": 40.0,
        "lomin": -118.0,
        "lomax": -114.0,
        "center": [37.5, -116.0],
        "zoom": 7,
    },
    "socal": {
        "name": "Southern California (Edwards AFB / Military)",
        "lamin": 33.0,
        "lamax": 36.0,
        "lomin": -120.0,
        "lomax": -116.0,
        "center": [34.5, -118.0],
        "zoom": 7,
    },
    "gulf": {
        "name": "Gulf of Mexico (Oil Rigs / Coast Guard)",
        "lamin": 25.0,
        "lamax": 31.0,
        "lomin": -97.0,
        "lomax": -85.0,
        "center": [28.0, -91.0],
        "zoom": 6,
    },
    "northeast_us": {
        "name": "US Northeast Corridor (NYC / DC / Boston)",
        "lamin": 38.0,
        "lamax": 43.0,
        "lomin": -77.0,
        "lomax": -71.0,
        "center": [40.5, -74.0],
        "zoom": 7,
    },
    "india": {
        "name": "Indian Subcontinent",
        "lamin": 8.0,
        "lamax": 35.0,
        "lomin": 68.0,
        "lomax": 97.0,
        "center": [22.0, 78.0],
        "zoom": 5,
    },
}

# Active region (change this to try different hunting grounds)
ACTIVE_REGION = "usa"

# ============================================================
# Data Collection Settings
# ============================================================
MAX_FLIGHTS = 175           # Expanded live sample to capture diverse aircraft types
TRACK_DELAY_SEC = 0.5       # Delay between API calls (respect rate limits)
MAX_RETRIES = 3             # Retry failed API calls this many times
RETRY_DELAY_SEC = 5         # Wait between retries
REQUEST_TIMEOUT_SEC = 30    # HTTP request timeout
TIME_WINDOW_HOURS = 2       # Look back this many hours for flights

# ============================================================
# Anomaly Detection Thresholds
# ============================================================
MIN_WAYPOINTS = 8           # Minimum waypoints to bother analyzing

# --- Circular / Holding Pattern ---
CIRCULAR_RETURN_DISTANCE_KM = 12.0
CIRCULAR_MIN_LOOPS = 2
CIRCULAR_MAX_BBOX_KM = 60.0 # Holding orbits confined to 60 km box

# --- Altitude Anomaly (Strict: only rapid drops/dives, NO routine climbs) ---
ALTITUDE_DROP_THRESHOLD_FT = 3500     # Must drop at least 3,500 ft
ALTITUDE_DROP_TIME_SEC = 90           # in under 90 seconds (steep dive)
ALTITUDE_MIN_RATE_FPM = 3500          # at least 3,500 ft/min descent rate
LOW_ALTITUDE_THRESHOLD_FT = 800
LOW_ALTITUDE_DURATION_SEC = 300

# --- Speed Anomaly ---
SPEED_ANOMALY_LOW_KT = 50
SPEED_ANOMALY_HIGH_KT = 680

# --- Loiter / Hovering (Calibrated for real flights & helicopters) ---
LOITER_MAX_BBOX_KM = 45.0             # Confined to 45 km area
LOITER_MIN_DURATION_MIN = 5.0         # For at least 5 minutes of recorded track

# --- Path Inefficiency ---
PATH_EFFICIENCY_THRESHOLD = 1.5       # 1.5x longer than direct line

# --- Zigzag / Heading Reversals ---
ZIGZAG_REVERSAL_ANGLE = 70            # Sharp 70+ deg turns across flight legs
ZIGZAG_MIN_REVERSALS = 2              # At least 2 reversals (swath / survey / grid pattern)
ZIGZAG_TIME_WINDOW_SEC = 600

# ============================================================
# Visualization Settings
# ============================================================
NORMAL_FLIGHT_COLOR = "#3d4f5f"
NORMAL_FLIGHT_OPACITY = 0.15
NORMAL_FLIGHT_WEIGHT = 1

ANOMALY_COLORS = {
    "circular":          "#ff3333",   # Red
    "altitude":          "#ff9900",   # Orange
    "loiter":            "#ff00ff",   # Magenta
    "zigzag":            "#00ffff",   # Cyan
    "path_inefficiency": "#ffff00",   # Yellow
    "speed":             "#00ff66",   # Green
    "low_altitude":      "#ff6600",   # Deep Orange
}

ANOMALY_WEIGHT = 3
ANOMALY_OPACITY = 0.85

MAP_TILES = "CartoDB dark_matter"
MAP_ZOOM = 4

# ============================================================
# Output Paths
# ============================================================
DATA_DIR = "data"
TRACKS_DIR = "data/tracks"
RESULTS_DIR = "data/results"
