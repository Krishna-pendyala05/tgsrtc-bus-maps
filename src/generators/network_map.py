"""
Network Map Generator
=====================
Generates a full network visualization showing all routes.

Features:
- All routes displayed on map
- Smart merging of bidirectional routes
- Search and filter functionality
- Route tooltips with details
"""

import json
from typing import Optional

from .base import BaseGenerator
from ..data.gtfs_loader import GTFSLoader
from ..utils.geo import calculate_route_overlap
from ..config import MERGE_THRESHOLD


class NetworkMapGenerator(BaseGenerator):
    """Generator for the full network map."""
    
    output_filename = "network_map.html"
    
    def generate(self) -> str:
        """Generate the network map HTML."""
        
        self._log_progress("Building network features...")
        features = self._build_features()
        
        self._log_progress(f"Generating HTML with {len(features)} routes...")
        return self._generate_html(features)
    
    def _build_features(self) -> list:
        """Build GeoJSON features for all routes."""
        import pandas as pd
        
        stops = self.loader.stops.copy()
        stop_times = self.loader.stop_times
        trips = self.loader.trips
        routes = self.loader.routes
        
        # Ensure numeric coords
        stops['stop_lat'] = pd.to_numeric(stops['stop_lat'], errors='coerce')
        stops['stop_lon'] = pd.to_numeric(stops['stop_lon'], errors='coerce')
        
        # Count stops per trip
        trip_counts = stop_times.groupby('trip_id').size().reset_index(name='stop_count')
        
        # Join with trips
        trips_enriched = trips.merge(trip_counts, on='trip_id')
        
        # Handle missing direction_id
        if 'direction_id' not in trips_enriched.columns:
            trips_enriched['direction_id'] = '0'
        trips_enriched['direction_id'] = trips_enriched['direction_id'].fillna('0')
        
        # Get representative trips
        rep_trips = (trips_enriched
                     .sort_values('stop_count', ascending=False)
                     .drop_duplicates(['route_id', 'direction_id']))
        
        self._log_progress(f"  Found {len(rep_trips)} representative trips")
        
        # Filter stop_times to representative trips
        trip_ids = set(rep_trips['trip_id'].unique())
        st_filtered = stop_times[stop_times['trip_id'].isin(trip_ids)].copy()
        st_filtered['stop_sequence'] = pd.to_numeric(st_filtered['stop_sequence'], errors='coerce').astype(int)
        
        # Join with stops
        st_geo = st_filtered.merge(
            stops[['stop_id', 'stop_name', 'stop_lat', 'stop_lon']], 
            on='stop_id', how='left'
        )
        
        # Build directions dict
        route_directions = {}
        for _, row in rep_trips.iterrows():
            trip_id = row['trip_id']
            route_id = row['route_id']
            direction_id = row['direction_id']
            
            trip_stops = st_geo[st_geo['trip_id'] == trip_id].sort_values('stop_sequence')
            
            if trip_stops.empty:
                continue
            
            coords = trip_stops[['stop_lon', 'stop_lat']].dropna().values.tolist()
            stop_ids = set(trip_stops['stop_id'].dropna().values)
            
            if route_id not in route_directions:
                route_directions[route_id] = {}
            
            route_directions[route_id][direction_id] = {
                'coords': coords,
                'stop_ids': stop_ids,
                'start': trip_stops.iloc[0]['stop_name'] if len(trip_stops) > 0 else 'Unknown',
                'end': trip_stops.iloc[-1]['stop_name'] if len(trip_stops) > 0 else 'Unknown',
                'count': len(coords)
            }
        
        # Build route names lookup
        route_names = {}
        for _, row in routes.iterrows():
            rid = row['route_id']
            name = row.get('route_short_name') or row.get('route_long_name') or rid
            route_names[rid] = str(name)
        
        # Create features with smart merging
        features = []
        
        for route_id, directions in route_directions.items():
            route_name = route_names.get(route_id, route_id)
            
            # Check for merge
            merged = False
            if '0' in directions and '1' in directions:
                s0 = directions['0']['stop_ids']
                s1 = directions['1']['stop_ids']
                
                jaccard = calculate_route_overlap(s0, s1)
                if jaccard > MERGE_THRESHOLD:
                    merged = True
                    
                    # Use longer direction
                    main_dir = '0' if directions['0']['count'] >= directions['1']['count'] else '1'
                    d = directions[main_dir]
                    
                    features.append({
                        "type": "Feature",
                        "properties": {
                            "route_name": str(route_name),
                            "search_key": f"{route_name} (Bidirectional)",
                            "details": f"{d['start']} ↔ {d['end']}",
                            "stops": d['count'],
                            "color": "#3388ff"
                        },
                        "geometry": {
                            "type": "LineString",
                            "coordinates": d['coords']
                        }
                    })
            
            if not merged:
                for dir_id, d in directions.items():
                    suffix = "(Outbound)" if dir_id == '0' else "(Inbound)"
                    color = "#ff3333" if dir_id == '0' else "#33aa33"
                    
                    features.append({
                        "type": "Feature",
                        "properties": {
                            "route_name": str(route_name),
                            "search_key": f"{route_name} {suffix}",
                            "details": f"{d['start']} → {d['end']}",
                            "stops": d['count'],
                            "color": color
                        },
                        "geometry": {
                            "type": "LineString",
                            "coordinates": d['coords']
                        }
                    })
        
        self._log_progress(f"  Generated {len(features)} features")
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
    <title>TGSRTC Full Network Map</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; }}
        
        #map {{ position: fixed; top: 0; left: 0; right: 0; bottom: 0; }}
        
        .control-panel {{
            position: fixed;
            top: 20px;
            left: 20px;
            z-index: 1000;
            background: white;
            padding: 20px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            width: 300px;
        }}
        
        .control-panel h1 {{
            font-size: 18px;
            margin-bottom: 15px;
            color: #333;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .search-box {{
            display: flex;
            gap: 8px;
        }}
        
        .search-box input {{
            flex: 1;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
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
            background: #e74c3c;
            color: white;
            font-weight: 600;
        }}
        
        .btn:hover {{
            background: #c0392b;
        }}
        
        .stats {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #eee;
            font-size: 13px;
            color: #666;
        }}
        
        .stats span {{
            font-weight: 600;
            color: #333;
        }}
        
        .legend {{
            margin-top: 15px;
            padding: 12px;
            background: #f8f9fa;
            border-radius: 8px;
            font-size: 12px;
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
    <h1>🌐 TGSRTC Network</h1>
    
    <div class="search-box">
        <input type="text" id="search" list="routes" placeholder="Search route...">
        <button class="btn" onclick="resetMap()">✕</button>
    </div>
    <datalist id="routes"></datalist>
    
    <div class="stats">
        Total Routes: <span id="totalRoutes">0</span>
    </div>
    
    <div class="legend">
        <div class="legend-item">
            <div class="legend-color" style="background: #3388ff;"></div>
            <span>Bidirectional</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #ff3333;"></div>
            <span>Outbound</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #33aa33;"></div>
            <span>Inbound</span>
        </div>
    </div>
</div>

<div id="map"></div>

<script>
const geojsonData = {json_str};

const map = L.map('map', {{
    center: [17.4, 78.5],
    zoom: 11,
    preferCanvas: true
}});

L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
    attribution: '© OpenStreetMap © CARTO',
    maxZoom: 19
}}).addTo(map);

const defaultStyle = {{ weight: 2, opacity: 0.5 }};
const highlightStyle = {{ weight: 5, opacity: 1 }};
const dimmedStyle = {{ weight: 1, opacity: 0.1 }};

let selectedKey = null;

const geoLayer = L.geoJSON(geojsonData, {{
    style: function(feature) {{
        return {{
            color: feature.properties.color,
            ...defaultStyle
        }};
    }},
    onEachFeature: function(feature, layer) {{
        const props = feature.properties;
        layer.bindTooltip(`<b>${{props.search_key}}</b><br>${{props.details}}<br>Stops: ${{props.stops}}`, {{
            sticky: true
        }});
        
        layer.on('click', function() {{
            selectRoute(props.search_key);
        }});
    }}
}}).addTo(map);

// Populate search datalist
const datalist = document.getElementById('routes');
geojsonData.features.forEach(f => {{
    const opt = document.createElement('option');
    opt.value = f.properties.search_key;
    datalist.appendChild(opt);
}});

document.getElementById('totalRoutes').textContent = geojsonData.features.length;

// Search handler
document.getElementById('search').addEventListener('input', function(e) {{
    const value = e.target.value;
    if (geojsonData.features.some(f => f.properties.search_key === value)) {{
        selectRoute(value);
    }}
}});

function selectRoute(searchKey) {{
    selectedKey = searchKey;
    
    geoLayer.eachLayer(layer => {{
        const isSelected = layer.feature.properties.search_key === searchKey;
        layer.setStyle({{
            color: layer.feature.properties.color,
            ...(isSelected ? highlightStyle : dimmedStyle)
        }});
        if (isSelected) {{
            layer.bringToFront();
            map.fitBounds(layer.getBounds(), {{ padding: [50, 50] }});
        }}
    }});
}}

function resetMap() {{
    selectedKey = null;
    document.getElementById('search').value = '';
    
    geoLayer.eachLayer(layer => {{
        layer.setStyle({{
            color: layer.feature.properties.color,
            ...defaultStyle
        }});
    }});
    
    map.setView([17.4, 78.5], 11);
}}
</script>
</body>
</html>'''
