"""
Interactive Map Generator
=========================
Generates an interactive bus route search map with spotlight mode.

Features:
- Route search with autocomplete
- Spotlight mode (selected route highlighted, others dimmed)
- Stop markers on route selection
- Responsive control panel
"""

import json
from typing import Optional

from .base import BaseGenerator
from ..data.gtfs_loader import GTFSLoader
from ..utils.geo import calculate_route_overlap
from ..config import MERGE_THRESHOLD


class InteractiveMapGenerator(BaseGenerator):
    """Generator for the interactive route search map."""
    
    output_filename = "interactive_map.html"
    
    def generate(self) -> str:
        """Generate the interactive map HTML."""
        
        self._log_progress("Extracting representative trips...")
        rep_trips = self.loader.get_representative_trips()
        
        self._log_progress("Building route geometries...")
        geometries = self._build_route_geometries(rep_trips)
        
        self._log_progress("Creating GeoJSON features with smart merging...")
        features = self._create_geojson_features(geometries)
        
        self._log_progress(f"Generating HTML with {len(features)} routes...")
        return self._generate_html(features)
    
    def _build_route_geometries(self, rep_trips) -> dict:
        """Build geometry and stop details for each representative trip."""
        import pandas as pd
        
        stops_df = self.loader.stops.copy()
        stops_df['stop_lat'] = pd.to_numeric(stops_df['stop_lat'], errors='coerce')
        stops_df['stop_lon'] = pd.to_numeric(stops_df['stop_lon'], errors='coerce')
        
        stop_times = self.loader.stop_times
        
        # Filter to representative trips
        trip_ids = set(rep_trips['trip_id'].unique())
        st_filtered = stop_times[stop_times['trip_id'].isin(trip_ids)].copy()
        st_filtered['stop_sequence'] = pd.to_numeric(st_filtered['stop_sequence'], errors='coerce').fillna(0).astype(int)
        
        # Merge with stops
        st_geo = st_filtered.merge(
            stops_df[['stop_id', 'stop_name', 'stop_lat', 'stop_lon']], 
            on='stop_id', how='left'
        )
        
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
        
        return geometries
    
    def _create_geojson_features(self, geometries: dict) -> list:
        """Create GeoJSON features with smart merging for bidirectional routes."""
        routes_df = self.loader.routes
        
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
                
                jaccard = calculate_route_overlap(s0, s1)
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
        
        # Sort by search_text
        features.sort(key=lambda x: x['properties']['search_text'])
        
        self._log_progress(f"  {merged_count} bidirectional routes")
        self._log_progress(f"  {split_count} one-way routes")
        
        return features
    
    def _generate_html(self, features: list) -> str:
        """Generate the complete HTML file."""
        
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
