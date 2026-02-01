"""
TGSRTC Trip Planner Generator (v3 - Location-Based Search)
============================================================
Major improvements:
1. LOCATION-BASED SEARCH - User selects locations, not directional stops
2. Automatically finds the correct directional stop pair
3. Shows all stops at that location grouped together
4. Map clears properly when changing search

Output: trip_planner.html
"""

import pandas as pd
import os
import json
import re
from pathlib import Path
from collections import defaultdict

# ============================================================================
# CONFIGURATION
# ============================================================================
DATA_DIR = Path('.')
OUTPUT_FILE = 'trip_planner.html'

GTFS_FILES = {
    'stops': 'stops.txt',
    'stop_times': 'stop_times.txt',
    'trips': 'trips.txt',
    'routes': 'routes.txt'
}

# ============================================================================
# DATA LOADING
# ============================================================================
def load_gtfs_data() -> dict:
    dfs = {}
    print("=" * 60)
    print("LOADING GTFS DATA")
    print("=" * 60)
    
    for name, filename in GTFS_FILES.items():
        path = DATA_DIR / filename
        if path.exists():
            print(f"  Loading {filename}...")
            dfs[name] = pd.read_csv(path, dtype=str)
            print(f"    → {len(dfs[name]):,} rows")
        else:
            print(f"  WARNING: {filename} not found!")
            
    return dfs

# ============================================================================
# EXTRACT BASE LOCATION NAME
# ============================================================================
def extract_base_name(stop_name: str) -> str:
    """
    Remove directional suffix like 'Twd Secunderabad' from stop name.
    'Uppal X Road Twd Secunderabad' → 'Uppal X Road'
    """
    # Pattern: anything followed by ' Twd ' and more text
    match = re.match(r'^(.+?)\s+Twd\s+.+$', stop_name, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return stop_name.strip()

# ============================================================================
# INDEX BUILDING
# ============================================================================
def build_indices(dfs: dict) -> dict:
    print("\n" + "=" * 60)
    print("BUILDING ROUTING INDICES")
    print("=" * 60)
    
    stops = dfs['stops']
    stop_times = dfs['stop_times']
    trips = dfs['trips']
    routes = dfs['routes']
    
    # 1. Stop data with base names
    print("  Building stop location index...")
    stop_names = {}  # stop_id -> full name
    stop_coords = {}  # stop_id -> [lat, lon]
    stop_base_names = {}  # stop_id -> base name (no direction)
    
    for _, row in stops.iterrows():
        sid = row['stop_id']
        full_name = row['stop_name']
        stop_names[sid] = full_name
        stop_base_names[sid] = extract_base_name(full_name)
        try:
            stop_coords[sid] = [float(row['stop_lat']), float(row['stop_lon'])]
        except:
            pass
    
    # 2. Build location groups (base_name -> [stop_ids])
    location_stops = defaultdict(list)
    for sid, base_name in stop_base_names.items():
        location_stops[base_name].append(sid)
    
    print(f"    → {len(stop_names):,} stops")
    print(f"    → {len(location_stops):,} unique locations")
    
    # Get average coords per location
    location_coords = {}
    for loc, sids in location_stops.items():
        coords_list = [stop_coords[sid] for sid in sids if sid in stop_coords]
        if coords_list:
            avg_lat = sum(c[0] for c in coords_list) / len(coords_list)
            avg_lon = sum(c[1] for c in coords_list) / len(coords_list)
            location_coords[loc] = [avg_lat, avg_lon]
    
    # 3. Route Names
    print("  Building route names index...")
    route_names = {}
    for _, row in routes.iterrows():
        rid = row['route_id']
        name = row.get('route_short_name') or row.get('route_long_name') or rid
        route_names[rid] = str(name)
    print(f"    → {len(route_names):,} routes")
    
    # 4. Trip to Route mapping
    print("  Mapping trips to routes...")
    trip_to_route = {}
    for _, row in trips.iterrows():
        trip_to_route[row['trip_id']] = row['route_id']
    
    # 5. Route-Stops sequences
    print("  Building route-stops sequences...")
    trip_stop_counts = stop_times.groupby('trip_id').size()
    
    route_rep_trips = {}
    for tid, cnt in trip_stop_counts.items():
        rid = trip_to_route.get(tid)
        if rid:
            if rid not in route_rep_trips or cnt > route_rep_trips[rid][1]:
                route_rep_trips[rid] = (tid, cnt)
    
    route_stops = {}
    route_stop_times = {}
    
    for rid, (tid, _) in route_rep_trips.items():
        trip_st = stop_times[stop_times['trip_id'] == tid].copy()
        trip_st['stop_sequence'] = pd.to_numeric(trip_st['stop_sequence'], errors='coerce')
        trip_st = trip_st.sort_values('stop_sequence')
        
        route_stops[rid] = trip_st['stop_id'].tolist()
        route_stop_times[rid] = [
            {
                'stop': row['stop_id'],
                'arr': row['arrival_time'],
                'dep': row['departure_time'],
                'seq': int(row['stop_sequence'])
            }
            for _, row in trip_st.iterrows()
        ]
    print(f"    → {len(route_stops):,} route sequences built")
    
    # 6. Stop-Routes index
    print("  Building stop-routes index...")
    stop_routes = defaultdict(set)
    for rid, stops_list in route_stops.items():
        for sid in stops_list:
            stop_routes[sid].add(rid)
    stop_routes = {k: list(v) for k, v in stop_routes.items()}
    
    # 7. Location-Routes index (which routes serve a location, considering all directional stops)
    print("  Building location-routes index...")
    location_routes = {}
    for loc, sids in location_stops.items():
        routes_at_loc = set()
        for sid in sids:
            routes_at_loc.update(stop_routes.get(sid, []))
        location_routes[loc] = list(routes_at_loc)
    print(f"    → {len(location_routes):,} locations with routes")
    
    # 8. Travel times
    print("  Calculating travel times...")
    
    def time_to_minutes(t):
        try:
            parts = t.split(':')
            return int(parts[0]) * 60 + int(parts[1])
        except:
            return None
    
    route_travel_times = {}
    for rid, times in route_stop_times.items():
        durations = []
        for i in range(len(times) - 1):
            t1 = time_to_minutes(times[i]['dep'])
            t2 = time_to_minutes(times[i + 1]['arr'])
            if t1 is not None and t2 is not None:
                diff = t2 - t1
                if diff < 0:
                    diff = 3
                durations.append(max(1, min(diff, 30)))  # 1-30 min range
            else:
                durations.append(3)
        route_travel_times[rid] = durations
    
    return {
        'stopNames': stop_names,
        'stopCoords': stop_coords,
        'stopBaseNames': stop_base_names,
        'locationStops': {k: v for k, v in location_stops.items()},
        'locationCoords': location_coords,
        'locationRoutes': location_routes,
        'routeNames': route_names,
        'routeStops': route_stops,
        'stopRoutes': stop_routes,
        'routeTravelTimes': route_travel_times
    }

# ============================================================================
# HTML GENERATION
# ============================================================================
def generate_html(indices: dict) -> str:
    # Sorted location list for autocomplete
    sorted_locations = sorted(indices['locationCoords'].keys())
    
    data_json = json.dumps({
        'stopNames': indices['stopNames'],
        'stopCoords': indices['stopCoords'],
        'stopBaseNames': indices['stopBaseNames'],
        'locationStops': indices['locationStops'],
        'locationCoords': indices['locationCoords'],
        'locationRoutes': indices['locationRoutes'],
        'routeNames': indices['routeNames'],
        'routeStops': indices['routeStops'],
        'stopRoutes': indices['stopRoutes'],
        'routeTravelTimes': indices['routeTravelTimes']
    }, ensure_ascii=False)
    
    locations_json = json.dumps(sorted_locations, ensure_ascii=False)
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TGSRTC Trip Planner</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f172a; }}
        
        .container {{ display: flex; height: 100vh; }}
        
        .panel {{
            width: 420px;
            background: linear-gradient(180deg, #1e293b 0%, #0f172a 100%);
            display: flex;
            flex-direction: column;
            z-index: 1000;
            border-right: 1px solid #334155;
        }}
        
        .panel-header {{
            padding: 24px;
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        }}
        
        .panel-header h1 {{ font-size: 24px; color: white; margin-bottom: 4px; }}
        .panel-header p {{ font-size: 14px; color: rgba(255,255,255,0.8); }}
        
        .search-form {{ padding: 20px; }}
        .input-group {{ margin-bottom: 16px; }}
        .input-group label {{ 
            display: block; 
            font-size: 11px; 
            color: #94a3b8; 
            margin-bottom: 6px; 
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .input-group input {{
            width: 100%;
            padding: 14px 16px;
            border: 2px solid #334155;
            border-radius: 10px;
            font-size: 15px;
            background: #1e293b;
            color: #f1f5f9;
            transition: all 0.2s;
        }}
        .input-group input:focus {{ 
            outline: none; 
            border-color: #6366f1;
            background: #0f172a;
        }}
        .input-group input::placeholder {{ color: #64748b; }}
        
        .btn {{
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            transition: all 0.2s;
        }}
        .btn:hover {{ 
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(99, 102, 241, 0.4);
        }}
        
        .results {{ flex: 1; overflow-y: auto; padding: 16px; }}
        
        .no-results {{ 
            text-align: center; 
            color: #64748b; 
            padding: 40px 20px;
        }}
        .no-results .icon {{ font-size: 56px; margin-bottom: 16px; opacity: 0.7; }}
        .no-results p {{ font-size: 14px; line-height: 1.6; }}
        
        .result-card {{
            background: #1e293b;
            border-radius: 14px;
            padding: 16px;
            margin-bottom: 12px;
            cursor: pointer;
            border: 2px solid #334155;
            transition: all 0.2s;
        }}
        .result-card:hover, .result-card.selected {{
            border-color: #6366f1;
            background: #1e293b;
            box-shadow: 0 4px 16px rgba(99, 102, 241, 0.2);
        }}
        
        .result-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }}
        .result-duration {{ font-size: 22px; font-weight: 700; color: #f1f5f9; }}
        .result-transfers {{ 
            font-size: 11px; 
            color: #6366f1; 
            background: rgba(99, 102, 241, 0.15); 
            padding: 5px 12px; 
            border-radius: 20px;
            font-weight: 600;
        }}
        
        .result-route {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
        .route-badge {{ 
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            color: white; 
            padding: 8px 14px; 
            border-radius: 8px; 
            font-weight: 700;
            font-size: 14px;
        }}
        .route-arrow {{ color: #475569; font-size: 18px; }}
        .result-details {{ 
            font-size: 12px; 
            color: #94a3b8; 
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid #334155;
        }}
        
        #map {{ flex: 1; }}
        
        .stop-tooltip {{
            background: #1e293b !important;
            color: #f1f5f9 !important;
            border: 1px solid #6366f1 !important;
            border-radius: 8px !important;
            padding: 6px 12px !important;
            font-size: 12px !important;
            font-weight: 600 !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4) !important;
        }}
        .stop-tooltip::before {{
            border-top-color: #6366f1 !important;
        }}
        
        .loading {{ display: none; text-align: center; padding: 24px; color: #94a3b8; }}
        .loading.active {{ display: block; }}
        .spinner {{
            width: 44px; height: 44px;
            border: 4px solid #334155; 
            border-top-color: #6366f1;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 12px;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        
        .help-text {{
            font-size: 11px;
            color: #64748b;
            margin-top: 8px;
            line-height: 1.5;
        }}
    </style>
</head>
<body>

<div class="container">
    <div class="panel">
        <div class="panel-header">
            <h1>🚌 TGSRTC Trip Planner</h1>
            <p>Find the best bus route between locations</p>
        </div>
        
        <div class="search-form">
            <div class="input-group">
                <label>📍 From</label>
                <input type="text" id="origin" list="locationsList" placeholder="Type a location name...">
            </div>
            <div class="input-group">
                <label>🎯 To</label>
                <input type="text" id="destination" list="locationsList" placeholder="Type a location name...">
            </div>
            <datalist id="locationsList"></datalist>
            <button class="btn" onclick="findRoutes()">
                <span>🔍</span> Find Routes
            </button>
            <div class="help-text">
                💡 Enter location names like "Secunderabad", "ECIL", "Mehdipatnam". 
                The system will automatically find the correct bus stops.
            </div>
        </div>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <div>Finding best routes...</div>
        </div>
        
        <div class="results" id="results">
            <div class="no-results">
                <div class="icon">🗺️</div>
                <p>Enter your starting point and destination to find bus routes.</p>
            </div>
        </div>
    </div>
    
    <div id="map"></div>
</div>

<script>
const DATA = {data_json};
const LOCATIONS = {locations_json};

// Map setup
const map = L.map('map').setView([17.4, 78.5], 11);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
    attribution: '© OpenStreetMap © CARTO',
    maxZoom: 19
}}).addTo(map);

let routeLayer = L.layerGroup().addTo(map);
let markersLayer = L.layerGroup().addTo(map);

// Location autocomplete
const datalist = document.getElementById('locationsList');
LOCATIONS.forEach(loc => {{
    const opt = document.createElement('option');
    opt.value = loc;
    datalist.appendChild(opt);
}});

function clearMap() {{
    routeLayer.clearLayers();
    markersLayer.clearLayers();
}}

// Find all stop_ids at a location
function getStopsAtLocation(locationName) {{
    return DATA.locationStops[locationName] || [];
}}

// Find routes connecting two locations
function findRoutesRaptor(originLoc, destLoc) {{
    const results = [];
    
    const originStops = new Set(getStopsAtLocation(originLoc));
    const destStops = new Set(getStopsAtLocation(destLoc));
    
    if (originStops.size === 0 || destStops.size === 0) {{
        return [];
    }}
    
    // Get all routes that serve origin and destination locations
    const originRoutes = new Set(DATA.locationRoutes[originLoc] || []);
    const destRoutes = new Set(DATA.locationRoutes[destLoc] || []);
    
    // Direct routes
    const directRoutes = [...originRoutes].filter(r => destRoutes.has(r));
    
    for (const routeId of directRoutes) {{
        const stops = DATA.routeStops[routeId];
        
        // Find first origin stop and last dest stop in this route
        let originIdx = -1, originStopId = null;
        let destIdx = -1, destStopId = null;
        
        for (let i = 0; i < stops.length; i++) {{
            const sid = stops[i];
            if (originStops.has(sid) && originIdx === -1) {{
                originIdx = i;
                originStopId = sid;
            }}
            if (destStops.has(sid) && i > originIdx && originIdx >= 0) {{
                destIdx = i;
                destStopId = sid;
            }}
        }}
        
        if (originIdx >= 0 && destIdx > originIdx) {{
            const travelTimes = DATA.routeTravelTimes[routeId] || [];
            let duration = 0;
            for (let i = originIdx; i < destIdx; i++) {{
                duration += travelTimes[i] || 3;
            }}
            
            results.push({{
                type: 'direct',
                routes: [routeId],
                segments: [{{ routeId, startIdx: originIdx, endIdx: destIdx }}],
                transfers: 0,
                duration: duration,
                stopCount: destIdx - originIdx + 1,
                originStopId,
                destStopId
            }});
        }}
    }}
    
    // One transfer routes (limit search)
    if (results.length < 3) {{
        for (const route1 of originRoutes) {{
            const stops1 = DATA.routeStops[route1] || [];
            
            let originIdx1 = -1, originStopId1 = null;
            for (let i = 0; i < stops1.length; i++) {{
                if (originStops.has(stops1[i])) {{
                    originIdx1 = i;
                    originStopId1 = stops1[i];
                    break;
                }}
            }}
            if (originIdx1 < 0) continue;
            
            // Check potential transfer stops (limit to first 20 after origin)
            for (let i = originIdx1 + 1; i < Math.min(stops1.length, originIdx1 + 20); i++) {{
                const transferStopId = stops1[i];
                const transferLoc = DATA.stopBaseNames[transferStopId];
                const transferRoutes = DATA.stopRoutes[transferStopId] || [];
                
                for (const route2 of transferRoutes) {{
                    if (route2 === route1) continue;
                    if (!destRoutes.has(route2)) continue;
                    
                    const stops2 = DATA.routeStops[route2] || [];
                    const transferIdx2 = stops2.indexOf(transferStopId);
                    
                    let destIdx2 = -1, destStopId2 = null;
                    for (let j = transferIdx2 + 1; j < stops2.length; j++) {{
                        if (destStops.has(stops2[j])) {{
                            destIdx2 = j;
                            destStopId2 = stops2[j];
                            break;
                        }}
                    }}
                    
                    if (transferIdx2 >= 0 && destIdx2 > transferIdx2) {{
                        const times1 = DATA.routeTravelTimes[route1] || [];
                        const times2 = DATA.routeTravelTimes[route2] || [];
                        
                        let dur1 = 0;
                        for (let j = originIdx1; j < i; j++) dur1 += times1[j] || 3;
                        
                        let dur2 = 0;
                        for (let j = transferIdx2; j < destIdx2; j++) dur2 += times2[j] || 3;
                        
                        results.push({{
                            type: 'transfer',
                            routes: [route1, route2],
                            segments: [
                                {{ routeId: route1, startIdx: originIdx1, endIdx: i }},
                                {{ routeId: route2, startIdx: transferIdx2, endIdx: destIdx2 }}
                            ],
                            transfers: 1,
                            duration: dur1 + 5 + dur2,
                            transferLoc: transferLoc,
                            transferStopId: transferStopId,
                            originStopId: originStopId1,
                            destStopId: destStopId2
                        }});
                    }}
                }}
            }}
        }}
    }}
    
    // Sort and dedupe
    results.sort((a, b) => a.duration - b.duration || a.transfers - b.transfers);
    
    const seen = new Set();
    const unique = [];
    for (const r of results) {{
        const key = r.routes.join('-');
        if (!seen.has(key)) {{
            seen.add(key);
            unique.push(r);
            if (unique.length >= 5) break;
        }}
    }}
    
    return unique;
}}

function findRoutes() {{
    const originLoc = document.getElementById('origin').value.trim();
    const destLoc = document.getElementById('destination').value.trim();
    
    // Clear map immediately
    clearMap();
    
    if (!LOCATIONS.includes(originLoc)) {{
        alert('Please select a valid origin from the suggestions');
        return;
    }}
    
    if (!LOCATIONS.includes(destLoc)) {{
        alert('Please select a valid destination from the suggestions');
        return;
    }}
    
    if (originLoc === destLoc) {{
        alert('Origin and destination cannot be the same');
        return;
    }}
    
    document.getElementById('loading').classList.add('active');
    document.getElementById('results').innerHTML = '';
    
    setTimeout(() => {{
        const results = findRoutesRaptor(originLoc, destLoc);
        document.getElementById('loading').classList.remove('active');
        displayResults(results, originLoc, destLoc);
    }}, 50);
}}

function displayResults(results, originLoc, destLoc) {{
    const container = document.getElementById('results');
    
    if (results.length === 0) {{
        container.innerHTML = `
            <div class="no-results">
                <div class="icon">😕</div>
                <p>No routes found between <strong>${{originLoc}}</strong> and <strong>${{destLoc}}</strong>.</p>
                <p style="margin-top: 8px;">Try nearby locations or check if there's a connecting route.</p>
            </div>
        `;
        return;
    }}
    
    container.innerHTML = results.map((r, idx) => `
        <div class="result-card" onclick="showRoute(${{idx}})" data-index="${{idx}}">
            <div class="result-header">
                <div class="result-duration">${{r.duration}} min</div>
                <div class="result-transfers">${{r.transfers === 0 ? '✓ Direct' : '↔ 1 Transfer'}}</div>
            </div>
            <div class="result-route">
                ${{r.routes.map(rid => `<span class="route-badge">${{DATA.routeNames[rid]}}</span>`).join('<span class="route-arrow">→</span>')}}
            </div>
            ${{r.transferLoc ? `<div class="result-details">🔄 Change at <strong>${{r.transferLoc}}</strong></div>` : ''}}
            ${{!r.transferLoc && r.stopCount ? `<div class="result-details">${{r.stopCount}} stops</div>` : ''}}
        </div>
    `).join('');
    
    window.currentResults = results;
    window.originLoc = originLoc;
    window.destLoc = destLoc;
    
    if (results.length > 0) showRoute(0);
}}

function showRoute(index) {{
    const result = window.currentResults[index];
    if (!result) return;
    
    document.querySelectorAll('.result-card').forEach((card, i) => {{
        card.classList.toggle('selected', i === index);
    }});
    
    clearMap();
    
    const bounds = L.latLngBounds();
    const colors = ['#6366f1', '#10b981'];
    
    // Draw segments
    result.segments.forEach((seg, segIdx) => {{
        const allStops = DATA.routeStops[seg.routeId];
        const segmentStops = allStops.slice(seg.startIdx, seg.endIdx + 1);
        
        // Build array with both coords and stop info
        const stopsWithCoords = segmentStops
            .map(sid => ({{ sid, coord: DATA.stopCoords[sid], name: DATA.stopNames[sid] }}))
            .filter(s => s.coord);
        
        const coords = stopsWithCoords.map(s => s.coord);
        
        if (coords.length > 1) {{
            L.polyline(coords, {{
                color: colors[segIdx % colors.length],
                weight: 6,
                opacity: 0.9
            }}).addTo(routeLayer);
            
            // Stop markers with tooltips
            stopsWithCoords.forEach((s, i) => {{
                if (i > 0 && i < stopsWithCoords.length - 1) {{
                    const marker = L.circleMarker(s.coord, {{
                        radius: 5,
                        color: '#fff',
                        weight: 2,
                        fillColor: colors[segIdx % colors.length],
                        fillOpacity: 1
                    }});
                    marker.bindTooltip(s.name || 'Stop', {{
                        permanent: false,
                        direction: 'top',
                        offset: [0, -8],
                        className: 'stop-tooltip'
                    }});
                    marker.addTo(routeLayer);
                }}
                bounds.extend(s.coord);
            }});
        }}
    }});
    
    // Origin marker - shows location name
    const originCoord = DATA.locationCoords[window.originLoc];
    if (originCoord) {{
        const originMarker = L.marker(originCoord, {{
            icon: L.divIcon({{
                className: '',
                html: `<div style="background:#22c55e;color:white;padding:8px 14px;border-radius:24px;font-weight:700;font-size:13px;white-space:nowrap;box-shadow:0 4px 12px rgba(0,0,0,0.4);">🚩 ${{window.originLoc}}</div>`,
                iconAnchor: [60, 15]
            }})
        }});
        originMarker.bindTooltip(window.originLoc, {{
            permanent: false,
            direction: 'top',
            offset: [0, -20],
            className: 'stop-tooltip'
        }});
        originMarker.addTo(markersLayer);
        bounds.extend(originCoord);
    }}
    
    // Destination marker - shows location name
    const destCoord = DATA.locationCoords[window.destLoc];
    if (destCoord) {{
        const destMarker = L.marker(destCoord, {{
            icon: L.divIcon({{
                className: '',
                html: `<div style="background:#ef4444;color:white;padding:8px 14px;border-radius:24px;font-weight:700;font-size:13px;white-space:nowrap;box-shadow:0 4px 12px rgba(0,0,0,0.4);">🏁 ${{window.destLoc}}</div>`,
                iconAnchor: [60, 15]
            }})
        }});
        destMarker.bindTooltip(window.destLoc, {{
            permanent: false,
            direction: 'top',
            offset: [0, -20],
            className: 'stop-tooltip'
        }});
        destMarker.addTo(markersLayer);
        bounds.extend(destCoord);
    }}
    
    // Transfer marker - shows transfer location name
    if (result.transferStopId) {{
        const transferCoord = DATA.stopCoords[result.transferStopId];
        const transferName = result.transferLoc || DATA.stopNames[result.transferStopId] || 'Transfer';
        if (transferCoord) {{
            const transferMarker = L.marker(transferCoord, {{
                icon: L.divIcon({{
                    className: '',
                    html: `<div style="background:#f59e0b;color:white;padding:8px 14px;border-radius:24px;font-weight:700;font-size:13px;white-space:nowrap;box-shadow:0 4px 12px rgba(0,0,0,0.4);">🔄 ${{transferName}}</div>`,
                    iconAnchor: [70, 15]
                }})
            }});
            transferMarker.bindTooltip(`Change bus at: ${{transferName}}`, {{
                permanent: false,
                direction: 'top',
                offset: [0, -20],
                className: 'stop-tooltip'
            }});
            transferMarker.addTo(markersLayer);
        }}
    }}
    
    if (bounds.isValid()) {{
        map.fitBounds(bounds, {{ padding: [80, 80] }});
    }}
}}
</script>
</body>
</html>'''

# ============================================================================
# MAIN
# ============================================================================
def main():
    print("\n" + "=" * 60)
    print("TGSRTC TRIP PLANNER (v3 - Location-Based)")
    print("=" * 60)
    
    dfs = load_gtfs_data()
    
    if not all(k in dfs for k in GTFS_FILES.keys()):
        print("\nERROR: Missing required GTFS files!")
        return
    
    indices = build_indices(dfs)
    
    print("\n" + "=" * 60)
    print("GENERATING HTML")
    print("=" * 60)
    
    html = generate_html(indices)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html)
    
    file_size = os.path.getsize(OUTPUT_FILE) / (1024 * 1024)
    print(f"\n  ✅ Saved: {OUTPUT_FILE}")
    print(f"  📦 Size: {file_size:.2f} MB")
    print("\n" + "=" * 60)
    print("COMPLETE!")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
