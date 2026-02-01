"""
TGSRTC GTFS Analyzer & Interactive Map Generator
=================================================
This single script:
1. Loads GTFS data (stops, routes, trips, stop_times)
2. Processes routes with "Smart Merging" (bidirectional detection)
3. Generates a single, self-contained interactive_map.html

Usage:
    python gtfs_map_generator.py

Output:
    interactive_map.html - A self-contained Leaflet.js map with:
        - Spotlight search functionality
        - Stop markers on route selection
        - Ghost mode for background context
"""

import pandas as pd
import os
import json
from pathlib import Path

# ============================================================================
# CONFIGURATION
# ============================================================================
DATA_DIR = Path('.')
OUTPUT_FILE = 'interactive_map.html'

GTFS_FILES = {
    'stops': 'stops.txt',
    'stop_times': 'stop_times.txt',
    'trips': 'trips.txt',
    'routes': 'routes.txt'
}

# Jaccard similarity threshold for merging bidirectional routes
MERGE_THRESHOLD = 0.3

# ============================================================================
# DATA LOADING
# ============================================================================
def load_gtfs_data() -> dict:
    """Load all GTFS files into DataFrames."""
    dfs = {}
    print("=" * 50)
    print("LOADING GTFS DATA")
    print("=" * 50)
    
    for name, filename in GTFS_FILES.items():
        path = DATA_DIR / filename
        if path.exists():
            print(f"  Loading {filename}...")
            dfs[name] = pd.read_csv(path, dtype=str)
            print(f"    -> {len(dfs[name]):,} rows, {len(dfs[name].columns)} columns")
        else:
            print(f"  WARNING: {filename} not found!")
            
    return dfs

# ============================================================================
# DATA PROCESSING
# ============================================================================
def extract_representative_trips(trips_df: pd.DataFrame, stop_times_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each (route_id, direction_id) pair, find the trip with the most stops.
    This serves as the "representative" geometry for that route direction.
    """
    print("\n  Counting stops per trip...")
    trip_stop_counts = stop_times_df.groupby('trip_id').size().reset_index(name='stop_count')
    
    trips_enriched = trips_df.merge(trip_stop_counts, on='trip_id', how='left')
    trips_enriched['stop_count'] = trips_enriched['stop_count'].fillna(0).astype(int)
    
    # Handle missing direction_id
    if 'direction_id' not in trips_enriched.columns:
        trips_enriched['direction_id'] = '0'
    trips_enriched['direction_id'] = trips_enriched['direction_id'].fillna('0')
    
    # Keep only the longest trip per (route, direction)
    rep_trips = (trips_enriched
                 .sort_values('stop_count', ascending=False)
                 .drop_duplicates(['route_id', 'direction_id']))
    
    print(f"    -> {len(rep_trips):,} representative trips extracted")
    return rep_trips

def build_route_geometries(rep_trips: pd.DataFrame, stop_times_df: pd.DataFrame, stops_df: pd.DataFrame) -> dict:
    """Build geometry and stop details for each representative trip."""
    print("\n  Building route geometries...")
    
    # Prepare stops with numeric coords
    stops_df = stops_df.copy()
    stops_df['stop_lat'] = pd.to_numeric(stops_df['stop_lat'], errors='coerce')
    stops_df['stop_lon'] = pd.to_numeric(stops_df['stop_lon'], errors='coerce')
    
    # Filter stop_times to only our representative trips
    trip_ids = set(rep_trips['trip_id'].unique())
    st_filtered = stop_times_df[stop_times_df['trip_id'].isin(trip_ids)].copy()
    st_filtered['stop_sequence'] = pd.to_numeric(st_filtered['stop_sequence'], errors='coerce').fillna(0).astype(int)
    
    # Merge with stops
    st_geo = st_filtered.merge(stops_df[['stop_id', 'stop_name', 'stop_lat', 'stop_lon']], on='stop_id', how='left')
    
    # Build geometry dict
    geometries = {}
    for _, row in rep_trips.iterrows():
        trip_id = row['trip_id']
        route_id = row['route_id']
        direction_id = row['direction_id']
        
        trip_stops = st_geo[st_geo['trip_id'] == trip_id].sort_values('stop_sequence')
        
        if trip_stops.empty:
            continue
            
        coords = trip_stops[['stop_lon', 'stop_lat']].dropna().values.tolist()
        stop_list = [
            {'name': r['stop_name'], 'lat': r['stop_lat'], 'lon': r['stop_lon']}
            for _, r in trip_stops.iterrows()
            if pd.notna(r['stop_lat']) and pd.notna(r['stop_lon'])
        ]
        
        key = (route_id, direction_id)
        geometries[key] = {
            'coords': coords,
            'stop_ids': set(trip_stops['stop_id'].dropna().values),
            'stop_list': stop_list,
            'start': trip_stops.iloc[0]['stop_name'] if len(trip_stops) > 0 else 'Unknown',
            'end': trip_stops.iloc[-1]['stop_name'] if len(trip_stops) > 0 else 'Unknown',
            'count': len(coords)
        }
    
    print(f"    -> {len(geometries)} geometries built")
    return geometries

def create_geojson_features(geometries: dict, routes_df: pd.DataFrame) -> list:
    """
    Create GeoJSON features with Smart Merging.
    If forward and reverse directions share >30% stops, merge them as "Bidirectional".
    """
    print("\n  Creating GeoJSON features with Smart Merging...")
    
    # Group by route_id
    route_directions = {}
    for (route_id, dir_id), data in geometries.items():
        if route_id not in route_directions:
            route_directions[route_id] = {}
        route_directions[route_id][dir_id] = data
    
    # Create route name lookup
    route_names = {}
    for _, row in routes_df.iterrows():
        rid = row['route_id']
        name = row.get('route_short_name') or row.get('route_long_name') or rid
        route_names[rid] = str(name)
    
    features = []
    merged_count = 0
    split_count = 0
    
    for route_id, directions in route_directions.items():
        route_name = route_names.get(route_id, route_id)
        
        # Check if we can merge
        merged = False
        if '0' in directions and '1' in directions:
            s0 = directions['0']['stop_ids']
            s1 = directions['1']['stop_ids']
            
            union_size = len(s0.union(s1))
            if union_size > 0:
                jaccard = len(s0.intersection(s1)) / union_size
                if jaccard > MERGE_THRESHOLD:
                    merged = True
                    merged_count += 1
                    
                    # Use the longer direction as representative
                    main_dir = '0' if directions['0']['count'] >= directions['1']['count'] else '1'
                    d = directions[main_dir]
                    
                    features.append({
                        "type": "Feature",
                        "properties": {
                            "id": f"{route_id}_bidir",
                            "route_name": route_name,
                            "search_text": f"{route_name} (Bidirectional)",
                            "desc": f"{d['start']} ↔ {d['end']}",
                            "stops_count": d['count'],
                            "stop_list": d['stop_list'],
                            "type": "bidirectional"
                        },
                        "geometry": {"type": "LineString", "coordinates": d['coords']}
                    })
        
        if not merged:
            for dir_id, d in directions.items():
                split_count += 1
                suffix = "Outbound" if dir_id == '0' else "Inbound"
                
                features.append({
                    "type": "Feature",
                    "properties": {
                        "id": f"{route_id}_{dir_id}",
                        "route_name": route_name,
                        "search_text": f"{route_name} ({suffix})",
                        "desc": f"{d['start']} → {d['end']}",
                        "stops_count": d['count'],
                        "stop_list": d['stop_list'],
                        "type": "one_way"
                    },
                    "geometry": {"type": "LineString", "coordinates": d['coords']}
                })
    
    # Sort by search_text for the datalist
    features.sort(key=lambda x: x['properties']['search_text'])
    
    print(f"    -> {merged_count} bidirectional routes")
    print(f"    -> {split_count} one-way/split routes")
    print(f"    -> {len(features)} total features")
    
    return features

# ============================================================================
# HTML GENERATION
# ============================================================================
def generate_html(features: list) -> str:
    """Generate the complete HTML file with embedded data and Leaflet.js code."""
    
    geojson = {"type": "FeatureCollection", "features": features}
    json_str = json.dumps(geojson, ensure_ascii=False)
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TGSRTC Bus Network - Interactive Map</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; }}
        
        #map {{ position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: 1; }}
        
        /* Control Panel */
        .control-panel {{
            position: fixed;
            top: 20px;
            left: 20px;
            z-index: 1000;
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            width: 320px;
            max-height: calc(100vh - 40px);
            overflow-y: auto;
        }}
        
        .panel-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }}
        
        .panel-header h1 {{
            font-size: 18px;
            color: #333;
            font-weight: 600;
        }}
        
        /* Search */
        .search-box {{
            display: flex;
            gap: 8px;
        }}
        
        .search-box input {{
            flex: 1;
            padding: 12px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            transition: border-color 0.2s;
        }}
        
        .search-box input:focus {{
            outline: none;
            border-color: #3498db;
        }}
        
        .btn {{
            padding: 12px 16px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            transition: all 0.2s;
        }}
        
        .btn-reset {{
            background: #e74c3c;
            color: white;
        }}
        
        .btn-reset:hover {{
            background: #c0392b;
            transform: scale(1.05);
        }}
        
        /* Route Info */
        .route-info {{
            margin-top: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
            display: none;
        }}
        
        .route-info.active {{ display: block; }}
        
        .info-row {{
            margin-bottom: 12px;
        }}
        
        .info-row:last-child {{ margin-bottom: 0; }}
        
        .info-label {{
            font-size: 11px;
            color: #888;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 3px;
        }}
        
        .info-value {{
            font-size: 15px;
            color: #333;
            font-weight: 500;
        }}
        
        /* Stats */
        .stats {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #eee;
            font-size: 12px;
            color: #888;
        }}
        
        .stats span {{
            font-weight: 600;
            color: #333;
        }}
        
        /* Legend */
        .legend {{
            margin-top: 15px;
            padding: 12px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 8px;
            color: white;
            font-size: 12px;
        }}
        
        .legend-title {{
            font-weight: 600;
            margin-bottom: 8px;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin: 4px 0;
        }}
        
        .legend-color {{
            width: 20px;
            height: 4px;
            border-radius: 2px;
        }}
    </style>
</head>
<body>

<div class="control-panel">
    <div class="panel-header">
        <span style="font-size: 24px;">🚌</span>
        <h1>TGSRTC Bus Network</h1>
    </div>
    
    <div class="search-box">
        <input type="text" id="search" list="routes" placeholder="Search route (e.g., 219)...">
        <button class="btn btn-reset" onclick="resetMap()" title="Reset View">✕</button>
    </div>
    <datalist id="routes"></datalist>
    
    <div class="route-info" id="routeInfo">
        <div class="info-row">
            <div class="info-label">Route</div>
            <div class="info-value" id="infoName">-</div>
        </div>
        <div class="info-row">
            <div class="info-label">Path</div>
            <div class="info-value" id="infoPath">-</div>
        </div>
        <div class="info-row">
            <div class="info-label">Stops</div>
            <div class="info-value" id="infoStops">-</div>
        </div>
    </div>
    
    <div class="stats">
        Total Routes: <span id="totalRoutes">0</span>
    </div>
    
    <div class="legend">
        <div class="legend-title">How to Use</div>
        <div class="legend-item">🔍 Search for a bus number</div>
        <div class="legend-item">🎯 Selected route highlights in red</div>
        <div class="legend-item">🚏 Orange dots show stops</div>
        <div class="legend-item">✕ Reset to see all routes</div>
    </div>
</div>

<div id="map"></div>

<script>
// ==========================================================================
// DATA
// ==========================================================================
const routesData = {json_str};

// ==========================================================================
// MAP INITIALIZATION
// ==========================================================================
const map = L.map('map', {{
    center: [17.4, 78.5],
    zoom: 11,
    zoomControl: false
}});

// Add zoom control to top-right
L.control.zoom({{ position: 'topright' }}).addTo(map);

// Light basemap for better contrast
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
    attribution: '© OpenStreetMap © CARTO',
    maxZoom: 19
}}).addTo(map);

// ==========================================================================
// STYLES
// ==========================================================================
const styles = {{
    default: {{ color: '#94a3b8', weight: 1.5, opacity: 0.4 }},
    highlight: {{ color: '#dc2626', weight: 5, opacity: 1 }},
    dimmed: {{ color: '#e2e8f0', weight: 1, opacity: 0.1 }}
}};

// ==========================================================================
// LAYERS
// ==========================================================================
let geoLayer;
let stopsLayer = L.layerGroup().addTo(map);
let selectedId = null;

function styleFeature(feature) {{
    if (!selectedId) return styles.default;
    return feature.properties.id === selectedId ? styles.highlight : styles.dimmed;
}}

geoLayer = L.geoJSON(routesData, {{
    style: styleFeature,
    onEachFeature: (feature, layer) => {{
        layer.bindTooltip(feature.properties.search_text, {{ sticky: true, className: 'route-tooltip' }});
        layer.on('click', () => selectRoute(feature));
    }}
}}).addTo(map);

// ==========================================================================
// SEARCH SETUP
// ==========================================================================
const searchInput = document.getElementById('search');
const datalist = document.getElementById('routes');
const routeInfo = document.getElementById('routeInfo');

// Populate datalist
routesData.features.forEach(f => {{
    const opt = document.createElement('option');
    opt.value = f.properties.search_text;
    datalist.appendChild(opt);
}});

document.getElementById('totalRoutes').textContent = routesData.features.length;

// Search event
searchInput.addEventListener('input', (e) => {{
    const feature = routesData.features.find(f => f.properties.search_text === e.target.value);
    if (feature) selectRoute(feature);
}});

// ==========================================================================
// ROUTE SELECTION
// ==========================================================================
function selectRoute(feature) {{
    selectedId = feature.properties.id;
    
    // Update line styles
    geoLayer.eachLayer(layer => {{
        const isSelected = layer.feature.properties.id === selectedId;
        layer.setStyle(isSelected ? styles.highlight : styles.dimmed);
        if (isSelected) {{
            layer.bringToFront();
            map.fitBounds(layer.getBounds(), {{ padding: [100, 100], maxZoom: 14 }});
        }}
    }});
    
    // Add stop markers
    stopsLayer.clearLayers();
    if (feature.properties.stop_list) {{
        feature.properties.stop_list.forEach((stop, idx) => {{
            if (stop.lat && stop.lon) {{
                const marker = L.circleMarker([stop.lat, stop.lon], {{
                    radius: 6,
                    color: '#fff',
                    weight: 2,
                    fillColor: '#f97316',
                    fillOpacity: 1
                }});
                marker.bindPopup(`<b>${{idx + 1}}. ${{stop.name}}</b>`);
                marker.addTo(stopsLayer);
            }}
        }});
    }}
    
    // Update info panel
    routeInfo.classList.add('active');
    document.getElementById('infoName').textContent = feature.properties.route_name;
    document.getElementById('infoPath').textContent = feature.properties.desc;
    document.getElementById('infoStops').textContent = feature.properties.stops_count;
}}

function resetMap() {{
    selectedId = null;
    searchInput.value = '';
    routeInfo.classList.remove('active');
    stopsLayer.clearLayers();
    
    geoLayer.eachLayer(layer => layer.setStyle(styles.default));
    map.setView([17.4, 78.5], 11);
}}
</script>
</body>
</html>'''

# ============================================================================
# MAIN
# ============================================================================
def main():
    print("\\n" + "=" * 50)
    print("TGSRTC GTFS MAP GENERATOR")
    print("=" * 50)
    
    # Load data
    dfs = load_gtfs_data()
    
    if not all(k in dfs for k in ['stops', 'stop_times', 'trips', 'routes']):
        print("\\nERROR: Missing required GTFS files!")
        return
    
    # Process
    print("\\n" + "=" * 50)
    print("PROCESSING DATA")
    print("=" * 50)
    
    rep_trips = extract_representative_trips(dfs['trips'], dfs['stop_times'])
    geometries = build_route_geometries(rep_trips, dfs['stop_times'], dfs['stops'])
    features = create_geojson_features(geometries, dfs['routes'])
    
    # Generate HTML
    print("\\n" + "=" * 50)
    print("GENERATING HTML")
    print("=" * 50)
    
    html = generate_html(features)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    
    file_size = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    print(f"\\n  ✅ Saved: {OUTPUT_FILE}")
    print(f"  📦 Size: {file_size:.2f} MB")
    print("\\n" + "=" * 50)
    print("COMPLETE!")
    print("=" * 50 + "\\n")

if __name__ == "__main__":
    main()
