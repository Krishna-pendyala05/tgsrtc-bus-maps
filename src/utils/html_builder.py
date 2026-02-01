"""
HTML Builder Utilities
======================
Shared utilities for generating HTML pages with Leaflet maps.
"""

from typing import Tuple, Optional


def get_base_styles() -> str:
    """
    Return common CSS styles used across all visualizations.
    
    Includes:
    - Dark theme base styles
    - Header/footer styling
    - Button and form styling
    - Responsive layouts
    """
    return '''
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background: #0f172a;
            color: #f1f5f9;
        }
        
        /* Header */
        .header {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            padding: 16px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid #334155;
            flex-wrap: wrap;
            gap: 12px;
        }
        
        .header h1 {
            font-size: 1.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #00ff88 0%, #00ffff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        /* Buttons */
        .btn {
            background: linear-gradient(135deg, #00ff88 0%, #00ffff 100%);
            color: #000;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            font-size: 0.95rem;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .btn:hover {
            transform: scale(1.05);
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.4);
        }
        
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        /* Map container */
        #map {
            height: calc(100vh - 70px);
            width: 100%;
            background: #1e293b;
        }
        
        /* Search/Input */
        .search-box {
            display: flex;
            gap: 8px;
        }
        
        .search-box input {
            background: #1e293b;
            border: 1px solid #334155;
            color: #f1f5f9;
            padding: 10px 16px;
            border-radius: 8px;
            font-size: 0.95rem;
            width: 250px;
        }
        
        .search-box input:focus {
            outline: none;
            border-color: #00ffff;
            box-shadow: 0 0 0 3px rgba(0, 255, 255, 0.1);
        }
        
        .search-box input::placeholder {
            color: #64748b;
        }
        
        /* Info panels */
        .info-panel {
            position: absolute;
            top: 80px;
            left: 16px;
            background: rgba(15, 23, 42, 0.95);
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 16px;
            max-width: 350px;
            max-height: calc(100vh - 120px);
            overflow-y: auto;
            z-index: 1000;
            backdrop-filter: blur(10px);
        }
        
        .info-panel.hidden {
            display: none;
        }
        
        /* Badges */
        .badge {
            display: inline-block;
            background: linear-gradient(135deg, #00ff88 0%, #00ffff 100%);
            color: #000;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        
        /* Custom Leaflet tooltip */
        .leaflet-tooltip {
            background: #1e293b;
            border: 1px solid #334155;
            color: #f1f5f9;
            border-radius: 6px;
            padding: 8px 12px;
            font-family: 'Inter', sans-serif;
        }
        
        .leaflet-tooltip::before {
            border-top-color: #334155;
        }
        
        /* Custom popup */
        .leaflet-popup-content-wrapper {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            color: #f1f5f9;
        }
        
        .leaflet-popup-tip {
            background: #1e293b;
            border: 1px solid #334155;
        }
        
        /* Route list items */
        .route-item {
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .route-item:hover {
            border-color: #00ff88;
            background: rgba(0, 255, 136, 0.1);
        }
        
        .route-item.active {
            border-color: #00ffff;
            background: rgba(0, 255, 255, 0.1);
        }
        
        /* Status messages */
        .status-msg {
            color: #64748b;
            text-align: center;
            padding: 20px;
        }
    '''


def get_leaflet_head(title: str, extra_styles: str = "") -> str:
    """
    Generate the HTML <head> section with Leaflet dependencies.
    
    Args:
        title: Page title
        extra_styles: Additional CSS to include
        
    Returns:
        HTML string for the <head> section
    """
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - TGSRTC</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.css"/>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        {get_base_styles()}
        {extra_styles}
    </style>
</head>'''


def get_leaflet_scripts(
    center: Tuple[float, float] = (17.385, 78.4867),
    zoom: int = 12,
    extra_scripts: str = ""
) -> str:
    """
    Generate the Leaflet initialization scripts.
    
    Args:
        center: Map center coordinates (lat, lon)
        zoom: Initial zoom level
        extra_scripts: Additional JavaScript to include
        
    Returns:
        HTML string with script tags
    """
    return f'''
    <script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.js"></script>
    <script>
        // Initialize map
        const map = L.map('map').setView([{center[0]}, {center[1]}], {zoom});
        
        // Dark tile layer
        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            attribution: '&copy; OpenStreetMap, &copy; CARTO',
            subdomains: 'abcd',
            maxZoom: 19
        }}).addTo(map);
        
        {extra_scripts}
    </script>'''


def build_leaflet_page(
    title: str,
    body_content: str,
    scripts: str,
    extra_styles: str = "",
    center: Tuple[float, float] = (17.385, 78.4867),
    zoom: int = 12
) -> str:
    """
    Generate a complete HTML page with Leaflet map.
    
    Args:
        title: Page title
        body_content: HTML content for the body
        scripts: Custom JavaScript (added after Leaflet init)
        extra_styles: Additional CSS styles
        center: Map center coordinates
        zoom: Initial zoom level
        
    Returns:
        Complete HTML page as string
    """
    head = get_leaflet_head(title, extra_styles)
    leaflet_scripts = get_leaflet_scripts(center, zoom, scripts)
    
    return f'''{head}
<body>
    {body_content}
    {leaflet_scripts}
</body>
</html>'''


def format_distance(km: float) -> str:
    """Format distance for display."""
    if km < 1:
        return f"{int(km * 1000)} m"
    return f"{km:.1f} km"


def format_time(minutes: int) -> str:
    """Format time duration for display."""
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m" if mins else f"{hours}h"
