"""
Nearby Stops Generator
======================
Generates a GPS-based stop finder.

Features:
- Find user's location via GPS
- Show nearest bus stops with distances
- Display routes at each stop
- Interactive map with custom markers
"""

import json
from typing import Optional
from collections import defaultdict

from .base import BaseGenerator
from ..data.gtfs_loader import GTFSLoader


class NearbyStopsGenerator(BaseGenerator):
    """Generator for the nearby stops finder."""
    
    output_filename = "nearby_stops.html"
    
    def generate(self) -> str:
        """Generate the nearby stops HTML."""
        
        self._log_progress("Building stop-routes mapping...")
        stops_data = self._build_stops_data()
        
        self._log_progress(f"Generating HTML with {len(stops_data)} stops...")
        return self._generate_html(stops_data)
    
    def _build_stops_data(self) -> list:
        """Build stops data with routes for each stop."""
        stops = self.loader.stops
        stop_times = self.loader.stop_times
        trips = self.loader.trips
        routes = self.loader.routes
        
        # Create trip_id -> route_id mapping
        trip_to_route = dict(zip(trips['trip_id'], trips['route_id']))
        
        # Create route_id -> route_name mapping
        route_name_col = 'route_short_name' if 'route_short_name' in routes.columns else 'route_long_name'
        route_names = dict(zip(routes['route_id'], routes[route_name_col]))
        
        # For each stop, find which routes stop there
        stop_routes = defaultdict(set)
        
        for _, row in stop_times.iterrows():
            stop_id = row['stop_id']
            trip_id = row['trip_id']
            
            if trip_id in trip_to_route:
                route_id = trip_to_route[trip_id]
                if route_id in route_names:
                    route_name = str(route_names[route_id])
                    stop_routes[stop_id].add(route_name)
        
        self._log_progress(f"  Mapped {len(stop_routes)} stops to routes")
        
        # Create stops data with routes
        stops_data = []
        for _, row in stops.iterrows():
            stop_id = row['stop_id']
            routes_at_stop = sorted(list(stop_routes.get(stop_id, set())))
            
            try:
                lat = float(row['stop_lat'])
                lon = float(row['stop_lon'])
            except:
                continue
            
            stops_data.append({
                'id': stop_id,
                'name': row['stop_name'],
                'lat': lat,
                'lon': lon,
                'routes': routes_at_stop
            })
        
        return stops_data
    
    def _generate_html(self, stops_data: list) -> str:
        """Generate the complete HTML file."""
        return self._get_html_template(json.dumps(stops_data))
    
    def _get_html_template(self, stops_json: str) -> str:
        """Return the HTML template with embedded data."""
        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bus Stops Near Me - TGSRTC</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.css"/>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', system-ui, sans-serif;
            background: #0f172a;
            color: #f1f5f9;
        }}
        
        .header {{
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            padding: 16px 20px;
            border-bottom: 1px solid #334155;
            display: flex;
            align-items: center;
            justify-content: space-between;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 1000;
        }}
        
        .header h1 {{
            font-size: 1.4rem;
            font-weight: 700;
            background: linear-gradient(135deg, #00ffff 0%, #ff0080 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .locate-btn {{
            background: linear-gradient(135deg, #00ffff 0%, #00ff88 100%);
            color: #000;
            border: none;
            padding: 10px 20px;
            border-radius: 25px;
            font-weight: 600;
            cursor: pointer;
            font-size: 0.95rem;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        
        .locate-btn:hover {{
            transform: scale(1.05);
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.4);
        }}
        
        .locate-btn:disabled {{
            opacity: 0.6;
            cursor: not-allowed;
        }}
        
        #map {{
            position: fixed;
            top: 68px;
            left: 0;
            right: 0;
            bottom: 0;
        }}
        
        .info-panel {{
            position: fixed;
            bottom: 20px;
            left: 20px;
            right: 20px;
            max-width: 400px;
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 20px;
            z-index: 1000;
            max-height: 300px;
            overflow-y: auto;
        }}
        
        .info-panel h3 {{
            color: #00ffff;
            margin-bottom: 12px;
            font-size: 1rem;
        }}
        
        .stop-item {{
            background: rgba(51, 65, 85, 0.5);
            border-radius: 10px;
            padding: 12px;
            margin-bottom: 10px;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid transparent;
        }}
        
        .stop-item:hover {{
            border-color: #00ff88;
            background: rgba(0, 255, 136, 0.1);
        }}
        
        .stop-name {{
            font-weight: 600;
            color: #f1f5f9;
            margin-bottom: 4px;
        }}
        
        .stop-distance {{
            font-size: 0.85rem;
            color: #00ff88;
            font-weight: 600;
        }}
        
        .stop-routes-preview {{
            font-size: 0.75rem;
            color: #94a3b8;
            margin-top: 4px;
        }}
        
        .status-msg {{
            color: #94a3b8;
            font-size: 0.9rem;
        }}
        
        .user-marker {{
            background: #ff0080;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            border: 3px solid #fff;
            box-shadow: 0 0 15px rgba(255, 0, 128, 0.8);
            animation: pulse 2s infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); box-shadow: 0 0 15px rgba(255, 0, 128, 0.8); }}
            50% {{ transform: scale(1.1); box-shadow: 0 0 25px rgba(255, 0, 128, 1); }}
        }}
        
        .stop-marker {{
            background: #00ffff;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            border: 2px solid #fff;
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.6);
        }}
        
        .stop-marker-far {{
            background: #6366f1;
        }}
        
        .stop-marker-selected {{
            background: #00ff88 !important;
            width: 24px !important;
            height: 24px !important;
            box-shadow: 0 0 30px rgba(0, 255, 136, 1) !important;
            animation: highlight 1.5s ease-in-out infinite;
            z-index: 1000 !important;
        }}
        
        @keyframes highlight {{
            0%, 100% {{ transform: scale(1); box-shadow: 0 0 30px rgba(0, 255, 136, 0.8); }}
            50% {{ transform: scale(1.3); box-shadow: 0 0 50px rgba(0, 255, 136, 1); }}
        }}
        
        .routes-popup {{
            background: #0f172a;
            border: 1px solid #00ff88;
            border-radius: 12px;
            padding: 12px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5), 0 0 20px rgba(0, 255, 136, 0.3);
            min-width: 200px;
            max-width: 280px;
        }}
        
        .routes-popup h4 {{
            color: #00ff88;
            font-size: 0.9rem;
            margin-bottom: 8px;
            border-bottom: 1px solid #334155;
            padding-bottom: 6px;
        }}
        
        .routes-popup .routes-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }}
        
        .routes-popup .route-badge {{
            background: linear-gradient(135deg, #00ff88 0%, #00ffff 100%);
            color: #000;
            padding: 4px 10px;
            border-radius: 15px;
            font-size: 0.75rem;
            font-weight: 700;
        }}
        
        .routes-popup .no-routes {{
            color: #94a3b8;
            font-size: 0.8rem;
            font-style: italic;
        }}
        
        .leaflet-popup-content-wrapper {{
            background: transparent;
            box-shadow: none;
            padding: 0;
        }}
        
        .leaflet-popup-content {{
            margin: 0;
        }}
        
        .leaflet-popup-tip {{
            background: #0f172a;
            border: 1px solid #00ff88;
        }}
        
        .leaflet-tooltip {{
            background: #1e293b;
            color: #f1f5f9;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 8px 12px;
            font-family: 'Inter', sans-serif;
            font-size: 0.85rem;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        }}
        
        .leaflet-tooltip::before {{
            border-top-color: #334155;
        }}
        
        .info-panel.hidden {{
            display: none;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📍 Bus Stops Near Me</h1>
        <button class="locate-btn" id="locateBtn" onclick="getLocation()">
            <span>📡</span> Find My Location
        </button>
    </div>
    
    <div id="map"></div>
    
    <div class="info-panel hidden" id="infoPanel">
        <h3>🚌 Nearest Bus Stops</h3>
        <div id="stopsList">
            <p class="status-msg">Click "Find My Location" to see nearby stops</p>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.3/dist/leaflet.js"></script>
    <script>
        const STOPS = {stops_json};
        
        const map = L.map('map').setView([17.385, 78.4867], 12);
        
        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
            maxZoom: 19
        }}).addTo(map);
        
        let userMarker = null;
        let stopMarkers = [];
        let nearestStopsData = [];
        
        function getDistance(lat1, lon1, lat2, lon2) {{
            const R = 6371;
            const dLat = (lat2 - lat1) * Math.PI / 180;
            const dLon = (lon2 - lon1) * Math.PI / 180;
            const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                      Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                      Math.sin(dLon/2) * Math.sin(dLon/2);
            const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
            return R * c;
        }}
        
        function formatDistance(km) {{
            if (km < 1) {{
                return Math.round(km * 1000) + ' m';
            }}
            return km.toFixed(1) + ' km';
        }}
        
        function getLocation() {{
            const btn = document.getElementById('locateBtn');
            btn.disabled = true;
            btn.innerHTML = '<span>⏳</span> Locating...';
            
            if (!navigator.geolocation) {{
                alert('Geolocation is not supported by your browser');
                btn.disabled = false;
                btn.innerHTML = '<span>📡</span> Find My Location';
                return;
            }}
            
            navigator.geolocation.getCurrentPosition(
                (position) => {{
                    const userLat = position.coords.latitude;
                    const userLon = position.coords.longitude;
                    showNearbyStops(userLat, userLon);
                    btn.disabled = false;
                    btn.innerHTML = '<span>📡</span> Update Location';
                }},
                (error) => {{
                    let msg = 'Unable to get your location.';
                    if (error.code === 1) msg = 'Location access denied. Please enable location permissions.';
                    else if (error.code === 2) msg = 'Location unavailable.';
                    else if (error.code === 3) msg = 'Location request timed out.';
                    alert(msg);
                    btn.disabled = false;
                    btn.innerHTML = '<span>📡</span> Find My Location';
                }},
                {{
                    enableHighAccuracy: true,
                    timeout: 10000,
                    maximumAge: 60000
                }}
            );
        }}
        
        function createRoutesPopup(stop) {{
            const routes = stop.routes || [];
            let routesHtml;
            
            if (routes.length === 0) {{
                routesHtml = '<p class="no-routes">No route data available</p>';
            }} else {{
                const badges = routes.slice(0, 15).map(r => `<span class="route-badge">${{r}}</span>`).join('');
                const moreText = routes.length > 15 ? `<span style="color:#94a3b8;font-size:0.7rem;margin-left:4px">+${{routes.length - 15}} more</span>` : '';
                routesHtml = `<div class="routes-list">${{badges}}${{moreText}}</div>`;
            }}
            
            return `
                <div class="routes-popup">
                    <h4>🚌 ${{stop.name}}</h4>
                    <div style="font-size:0.75rem;color:#00ffff;margin-bottom:8px;">
                        ${{routes.length}} bus route${{routes.length !== 1 ? 's' : ''}} stop here
                    </div>
                    ${{routesHtml}}
                </div>
            `;
        }}
        
        function showNearbyStops(userLat, userLon) {{
            if (userMarker) map.removeLayer(userMarker);
            stopMarkers.forEach(m => map.removeLayer(m));
            stopMarkers = [];
            
            userMarker = L.marker([userLat, userLon], {{
                icon: L.divIcon({{
                    className: '',
                    html: '<div class="user-marker"></div>',
                    iconSize: [20, 20],
                    iconAnchor: [10, 10]
                }})
            }}).addTo(map).bindTooltip('📍 You are here', {{permanent: false}});
            
            const stopsWithDistance = STOPS.map(stop => ({{
                ...stop,
                distance: getDistance(userLat, userLon, stop.lat, stop.lon)
            }})).sort((a, b) => a.distance - b.distance);
            
            nearestStopsData = stopsWithDistance.slice(0, 20);
            
            nearestStopsData.forEach((stop, i) => {{
                const isFar = stop.distance > 1;
                const marker = L.marker([stop.lat, stop.lon], {{
                    icon: L.divIcon({{
                        className: '',
                        html: `<div class="stop-marker ${{isFar ? 'stop-marker-far' : ''}}" data-index="${{i}}"></div>`,
                        iconSize: [12, 12],
                        iconAnchor: [6, 6]
                    }})
                }}).addTo(map);
                
                marker.bindPopup(createRoutesPopup(stop), {{
                    closeButton: true,
                    className: 'routes-popup-container'
                }});
                
                stopMarkers.push(marker);
            }});
            
            const panel = document.getElementById('infoPanel');
            const list = document.getElementById('stopsList');
            panel.classList.remove('hidden');
            
            list.innerHTML = nearestStopsData.slice(0, 10).map((stop, i) => {{
                const routePreview = stop.routes.length > 0 
                    ? `🚌 ${{stop.routes.slice(0, 5).join(', ')}}${{stop.routes.length > 5 ? '...' : ''}}`
                    : '';
                return `
                    <div class="stop-item" onclick="flyTo(${{stop.lat}}, ${{stop.lon}}, ${{i}})">
                        <div class="stop-name">${{i + 1}}. ${{stop.name}}</div>
                        <div class="stop-distance">📍 ${{formatDistance(stop.distance)}}</div>
                        ${{routePreview ? `<div class="stop-routes-preview">${{routePreview}}</div>` : ''}}
                    </div>
                `;
            }}).join('');
            
            const bounds = L.latLngBounds([[userLat, userLon]]);
            nearestStopsData.slice(0, 5).forEach(s => bounds.extend([s.lat, s.lon]));
            map.fitBounds(bounds, {{padding: [50, 50]}});
        }}
        
        let selectedMarkerElement = null;
        
        function flyTo(lat, lon, index) {{
            if (selectedMarkerElement) {{
                selectedMarkerElement.classList.remove('stop-marker-selected');
            }}
            
            if (index !== undefined && stopMarkers[index]) {{
                const markerEl = stopMarkers[index].getElement();
                if (markerEl) {{
                    const stopEl = markerEl.querySelector('.stop-marker');
                    if (stopEl) {{
                        stopEl.classList.add('stop-marker-selected');
                        selectedMarkerElement = stopEl;
                    }}
                }}
                
                map.flyTo([lat, lon], 17, {{duration: 1}});
                
                setTimeout(() => {{
                    stopMarkers[index].openPopup();
                }}, 1100);
            }} else {{
                map.flyTo([lat, lon], 17, {{duration: 1}});
            }}
        }}
    </script>
</body>
</html>'''
