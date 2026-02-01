
import pandas as pd
import os
import json

DATA_DIR = '.'
files = {
    'stops': 'stops.txt',
    'stop_times': 'stop_times.txt',
    'trips': 'trips.txt',
    'routes': 'routes.txt'
}

def load_data():
    dfs = {}
    print("Loading data...")
    for name, filename in files.items():
        path = os.path.join(DATA_DIR, filename)
        if os.path.exists(path):
            print(f"Loading {name}...")
            dfs[name] = pd.read_csv(path, dtype=str)
        else:
            print(f"WARNING: {filename} missing!")
    return dfs

def process_routes_to_geojson(dfs):
    stops = dfs['stops']
    stop_times = dfs['stop_times']
    trips = dfs['trips']
    routes = dfs['routes']
    
    # 1. Prepare Trip Data (Counts)
    print("Counting stops per trip...")
    trip_counts = stop_times.groupby('trip_id').size().reset_index(name='stop_count')
    trips_enriched = trips.merge(trip_counts, on='trip_id')
    if 'direction_id' not in trips_enriched.columns:
        trips_enriched['direction_id'] = '0'
    trips_enriched['direction_id'] = trips_enriched['direction_id'].fillna('0')

    # 2. Extract Representative Trips
    print("Extracting representative trips...")
    rep_trips = trips_enriched.sort_values('stop_count', ascending=False).drop_duplicates(['route_id', 'direction_id'])
    
    # 3. Get Geometry
    target_trip_ids = rep_trips['trip_id'].unique()
    st_filtered = stop_times[stop_times['trip_id'].isin(target_trip_ids)].copy()
    st_filtered['stop_sequence'] = st_filtered['stop_sequence'].astype(int)
    
    stops['stop_lat'] = stops['stop_lat'].astype(float)
    stops['stop_lon'] = stops['stop_lon'].astype(float)
    
    st_geo = st_filtered.merge(stops[['stop_id', 'stop_name', 'stop_lat', 'stop_lon']], on='stop_id')
    
    # 4. Smart Merging & Feature Generation
    features = []
    print("Processing and merging routes...")
    
    for route_id, group in rep_trips.groupby('route_id'):
        directions = {}
        for _, row in group.iterrows():
            d_id = row['direction_id']
            t_id = row['trip_id']
            trip_st = st_geo[st_geo['trip_id'] == t_id].sort_values('stop_sequence')
            if trip_st.empty: continue
            
            coords = trip_st[['stop_lon', 'stop_lat']].values.tolist()
            
            # Extract stop details for markers
            stop_details = []
            for _, s_row in trip_st.iterrows():
               stop_details.append({
                   'name': s_row['stop_name'],
                   'lat': s_row['stop_lat'],
                   'lon': s_row['stop_lon']
               })
               
            stop_ids = set(trip_st['stop_id'].values)
            start = trip_st.iloc[0]['stop_name']
            end = trip_st.iloc[-1]['stop_name']
            
            directions[d_id] = {
                'coords': coords, 
                'ids': stop_ids, 
                'start': start, 
                'end': end, 
                'cnt': len(coords),
                'stops': stop_details
            }
            
        r_info = routes[routes['route_id'] == route_id].iloc[0]
        r_name = r_info.get('route_short_name', r_info.get('route_long_name', route_id))
        
        merged = False
        if '0' in directions and '1' in directions:
            # Jaccard Sim
            s0, s1 = directions['0']['ids'], directions['1']['ids']
            if len(s0.union(s1)) > 0 and len(s0.intersection(s1)) / len(s0.union(s1)) > 0.3:
                merged = True
                d_main = '0' if directions['0']['cnt'] >= directions['1']['cnt'] else '1'
                d = directions[d_main]
                
                feat = {
                    "type": "Feature",
                    "properties": {
                        "id": f"{route_id}_bidir",
                        "route_name": str(r_name),
                        "search_text": f"{r_name} (Bidirectional)",
                        "desc": f"{d['start']} <-> {d['end']}",
                        "stops_count": d['cnt'],
                        "type": "bidirectional",
                        "stop_list": d['stops'] # Add stops list
                    },
                    "geometry": {"type": "LineString", "coordinates": d['coords']}
                }
                features.append(feat)

        if not merged:
            for d_id, d in directions.items():
                suffix = "Outbound" if d_id == '0' else "Inbound"
                feat = {
                    "type": "Feature",
                    "properties": {
                        "id": f"{route_id}_{d_id}",
                        "route_name": str(r_name),
                        "search_text": f"{r_name} ({suffix})",
                        "desc": f"{d['start']} -> {d['end']}",
                        "stops_count": d['cnt'],
                        "type": "one_way",
                        "stop_list": d['stops'] # Add stops list
                    },
                    "geometry": {"type": "LineString", "coordinates": d['coords']}
                }
                features.append(feat)
                
    return {"type": "FeatureCollection", "features": features}

def generate_html(geojson_data):
    print("Generating HTML...")
    
    # Sort features by search_text for the datalist
    geojson_data['features'].sort(key=lambda x: x['properties']['search_text'])
    
    # We embed the JSON directly into the HTML to avoid local CORS issues
    json_str = json.dumps(geojson_data)
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>TGSRTC Network Map - Spotlight Mode</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body {{ margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
        #map {{ position: absolute; top: 0; bottom: 0; width: 100%; z-index: 1; }}
        
        #controls {{
            position: absolute;
            top: 20px;
            left: 20px;
            z-index: 1000;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
            width: 300px;
        }}
        
        h2 {{ margin: 0 0 10px 0; font-size: 18px; color: #333; }}
        
        .search-container {{ display: flex; gap: 5px; }}
        
        input[type="text"] {{
            flex-grow: 1;
            padding: 8px;
            border: 1px solid #ccc;
            border-radius: 4px;
            font-size: 14px;
        }}
        
        button {{
            padding: 8px 12px;
            background: #e74c3c;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
        }}
        
        button:hover {{ background: #c0392b; }}
        
        #route-info {{
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #eee;
            display: none;
        }}
        
        .info-label {{ font-size: 12px; color: #666; font-weight: bold; text-transform: uppercase; margin-bottom: 2px; }}
        .info-value {{ font-size: 16px; color: #222; margin-bottom: 10px; }}
        
        .legend {{ font-size: 12px; margin-top: 10px; color: #666; font-style: italic; }}

    </style>
</head>
<body>

<div id="controls">
    <h2>🚌 Bus Route Spotlight</h2>
    <div class="search-container">
        <input type="text" id="routeSearch" list="routeList" placeholder="Search route (e.g. 219)...">
        <button onclick="resetMap()">X</button>
    </div>
    <datalist id="routeList">
        <!-- populated by JS -->
    </datalist>
    
    <div id="route-info">
        <div class="info-label">Route</div>
        <div class="info-value" id="d-name">-</div>
        
        <div class="info-label">Path</div>
        <div class="info-value" id="d-desc">-</div>
        
        <div class="info-label">Total Stops</div>
        <div class="info-value" id="d-stops">-</div>
    </div>
    
    <div class="legend">
        Tip: Search to focus. Stops appear on zoom.
    </div>
</div>

<div id="map"></div>

<script>
    // 1. Data Injection
    const routesData = {json_str};

    // 2. Map Initialization
    const map = L.map('map').setView([17.4, 78.5], 11);
    
    L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
    }}).addTo(map);

    // 3. Style Functions
    const defaultStyle = {{
        color: '#888',
        weight: 1,
        opacity: 0.3
    }};

    const highlightStyle = {{
        color: '#e74c3c', // Bright Red
        weight: 5,
        opacity: 1.0
    }};
    
    const dimmedStyle = {{
        color: '#ccc',
        weight: 1,
        opacity: 0.05 // Almost invisible
    }};

    // 4. Layer Setup
    let geoJsonLayer;
    let stopLayerGroup = L.layerGroup().addTo(map); // Layer for stop markers
    let selectedRouteId = null;

    function onEachFeature(feature, layer) {{
        // Tooltip logic
        layer.bindTooltip(feature.properties.search_text, {{ sticky: true }});
        
        // Click logic
        layer.on('click', function() {{
            selectRoute(feature);
        }});
    }}

    geoJsonLayer = L.geoJSON(routesData, {{
        style: defaultStyle,
        onEachFeature: onEachFeature
    }}).addTo(map);

    // 5. Populate Search Datalist
    const datalist = document.getElementById('routeList');
    routesData.features.forEach(f => {{
        const opt = document.createElement('option');
        opt.value = f.properties.search_text;
        datalist.appendChild(opt);
    }});

    // 6. Search Logic
    const searchInput = document.getElementById('routeSearch');
    
    searchInput.addEventListener('input', function(e) {{
        const val = e.target.value;
        const feature = routesData.features.find(f => f.properties.search_text === val);
        if (feature) {{
            selectRoute(feature);
        }}
    }});
    
    function selectRoute(feature) {{
        selectedRouteId = feature.properties.id;
        
        // Update Styles for Lines
        geoJsonLayer.eachLayer(layer => {{
            if (layer.feature.properties.id === selectedRouteId) {{
                layer.setStyle(highlightStyle);
                layer.bringToFront();
                map.fitBounds(layer.getBounds(), {{ padding: [50, 50], maxZoom: 14 }});
            }} else {{
                layer.setStyle(dimmedStyle);
            }}
        }});
        
        // Render Stops
        stopLayerGroup.clearLayers(); // Clear old stops
        
        if (feature.properties.stop_list) {{
            feature.properties.stop_list.forEach(stop => {{
                const circle = L.circleMarker([stop.lat, stop.lon], {{
                    radius: 5,
                    color: 'white',
                    weight: 1,
                    fillColor: '#d35400', // Pumpkin Orange
                    fillOpacity: 1.0
                }});
                circle.bindPopup("<b>" + stop.name + "</b>");
                circle.addTo(stopLayerGroup);
            }});
        }}
        
        // Update Info Box
        document.getElementById('route-info').style.display = 'block';
        document.getElementById('d-name').innerText = feature.properties.route_name;
        document.getElementById('d-desc').innerText = feature.properties.desc;
        document.getElementById('d-stops').innerText = feature.properties.stops_count;
    }}

    function resetMap() {{
        selectedRouteId = null;
        searchInput.value = '';
        document.getElementById('route-info').style.display = 'none';
        
        // Reset Styles
        geoJsonLayer.eachLayer(layer => {{
            layer.setStyle(defaultStyle);
        }});
        
        // Start view
        map.setView([17.4, 78.5], 11);
        
        // Clear stops
        stopLayerGroup.clearLayers();
    }}

</script>
</body>
</html>
    """
    
    with open('interactive_map.html', 'w', encoding='utf-8') as f:
        f.write(html_content)
    print("Saved interactive_map.html")

if __name__ == "__main__":
    dfs = load_data()
    geojson = process_routes_to_geojson(dfs)
    generate_html(geojson)
