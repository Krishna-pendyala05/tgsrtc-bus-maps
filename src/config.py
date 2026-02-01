"""
Configuration and Constants
============================
Centralized configuration for the TGSRTC GTFS Analyzer.
"""

from pathlib import Path

# ============================================================================
# PATHS
# ============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
WEB_DIR = PROJECT_ROOT / "web"
CACHE_DIR = PROJECT_ROOT / "cache"

# ============================================================================
# GTFS FILE DEFINITIONS
# ============================================================================

GTFS_FILES = {
    'stops': 'stops.txt',
    'stop_times': 'stop_times.txt',
    'trips': 'trips.txt',
    'routes': 'routes.txt',
    'agency': 'agency.txt',
    'calendar': 'calendar.txt',
    'feed_info': 'feed_info.txt'
}

# Column data types for consistent loading
GTFS_DTYPES = {
    'trip_id': str,
    'route_id': str,
    'stop_id': str,
    'service_id': str,
    'shape_id': str,
    'direction_id': str,
    'stop_sequence': int
}

# ============================================================================
# ALGORITHM PARAMETERS
# ============================================================================

# Smart merge threshold - routes with >30% stop overlap are merged as bidirectional
MERGE_THRESHOLD = 0.3

# Default map center (Hyderabad city center)
DEFAULT_MAP_CENTER = (17.385, 78.4867)
DEFAULT_ZOOM = 12

# ============================================================================
# WEB SCRAPER SETTINGS
# ============================================================================

SCRAPER_BASE_URL = "https://hyderabadcitybus.in"
SCRAPER_DELAY = 0.5  # Delay between requests in seconds
