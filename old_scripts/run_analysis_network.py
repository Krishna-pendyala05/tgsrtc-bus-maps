
import pandas as pd
import folium
from folium.plugins import Search
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
            dfs[name] = pd.read_csv(path, dtype=str) # Read all as string to be safe
            print(f"  {name}: {dfs[name].shape}")
        else:
            print(f"WARNING: {filename} missing!")
    return dfs

def create_network_map(dfs):
    stops = dfs['stops']
    stop_times = dfs['stop_times']
    trips = dfs['trips']
    routes = dfs['routes']
    
    # 1. Prepare Trip Data
    # We need to find the "Representative Trip" for each Route + Direction
    # Heuristic: The trip with the most stops is usually the main trunk route.
    
    print("Counting stops per trip...")
    # Group by trip_id and count stops
    trip_counts = stop_times.groupby('trip_id').size().reset_index(name='stop_count')
    
    # Join with trips to get route_id and direction_id
    trips_enriched = trips.merge(trip_counts, on='trip_id')
    
    # Fill direction_id if missing (assume 0 if n/a)
    if 'direction_id' not in trips_enriched.columns:
        trips_enriched['direction_id'] = '0'
    trips_enriched['direction_id'] = trips_enriched['direction_id'].fillna('0')

    # 2. Extract Representative Trips
    print("Extracting representative trips...")
    # Sort by stop_count desc, then drop duplicates to keep the longest trip per route+direction
    rep_trips = trips_enriched.sort_values('stop_count', ascending=False).drop_duplicates(['route_id', 'direction_id'])
    print(f"Found {len(rep_trips)} representative trips (across all directions).")

    # 3. Get Geometry (Lat/Lons) for each Rep Trip
    # We need stop sequences for these trips
    
    # Filter stop_times to just these trips to save memory
    target_trip_ids = rep_trips['trip_id'].unique()
    st_filtered = stop_times[stop_times['trip_id'].isin(target_trip_ids)].copy()
    
    # Convert stop_sequence to int for sorting
    st_filtered['stop_sequence'] = st_filtered['stop_sequence'].astype(int)
    
    # Join with stops to get Lat/Lon
    # Ensure lat/lon are floats
    stops['stop_lat'] = stops['stop_lat'].astype(float)
    stops['stop_lon'] = stops['stop_lon'].astype(float)
    
    st_geo = st_filtered.merge(stops[['stop_id', 'stop_name', 'stop_lat', 'stop_lon']], on='stop_id')
    
    # 4. Smart Merging Logic
    # Group by RouteID and compare Dir 0 vs Dir 1
    
    features = []
    
    route_groups = rep_trips.groupby('route_id')
    
    print("Processing routes and checking for symmetry...")
    
    for route_id, group in route_groups:
        # group has 1 or 2 rows (Dir 0, Dir 1)
        
        directions = {} # dir_id -> {points: [], stops: set()}
        
        for _, row in group.iterrows():
            d_id = row['direction_id']
            t_id = row['trip_id']
            
            # Get geometry
            # Sort by sequence
            trip_st = st_geo[st_geo['trip_id'] == t_id].sort_values('stop_sequence')
            
            if trip_st.empty: continue
            
            coords = trip_st[['stop_lon', 'stop_lat']].values.tolist() # GeoJSON is Lon, Lat
            stop_ids = set(trip_st['stop_id'].values)
            
            start_name = trip_st.iloc[0]['stop_name']
            end_name = trip_st.iloc[-1]['stop_name']
            
            directions[d_id] = {
                'coords': coords,
                'stop_ids': stop_ids,
                'start': start_name,
                'end': end_name,
                'count': len(coords)
            }
            
        # Comparison
        route_info = routes[routes['route_id'] == route_id].iloc[0]
        r_name = route_info.get('route_short_name', route_info.get('route_long_name', route_id))
        
        # Decide: Merge or Split?
        merged = False
        if '0' in directions and '1' in directions:
            s0 = directions['0']['stop_ids']
            s1 = directions['1']['stop_ids']
            
            # Jaccard Similarity
            intersection = len(s0.intersection(s1))
            union = len(s0.union(s1))
            jaccard = intersection / union if union > 0 else 0
            
            # If highly similar, or if one is subset of other, merge.
            # 0.5 is actually a high threshold for bus routes because return stops often have different IDs 
            # even if across the street. Let's use 0.3 as a heuristic for "Same Corridor".
            # Or better: check start/end. Start0 ~ End1?
            
            if jaccard > 0.3: 
                merged = True
                
                # Use the longer one as the geometry
                d_main = '0' if directions['0']['count'] >= directions['1']['count'] else '1'
                props = directions[d_main]
                
                feat = {
                    "type": "Feature",
                    "properties": {
                        "route_name": str(r_name),
                        "search_key": f"{r_name} (Bidirectional)",
                        "details": f"{props['start']} <-> {props['end']}",
                        "stops": props['count'],
                        "color": "#3388ff" # Blue
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": props['coords']
                    }
                }
                features.append(feat)
                
        if not merged:
            # Add each existing direction separately
            for d_id, data in directions.items():
                suffix = "(Outbound)" if d_id == '0' else "(Inbound)"
                feat = {
                    "type": "Feature",
                    "properties": {
                        "route_name": str(r_name),
                        "search_key": f"{r_name} {suffix}",
                        "details": f"{data['start']} -> {data['end']}",
                        "stops": data['count'],
                        "color": "#ff3333" if d_id == '0' else "#33aa33" # Red/Green
                    },
                    "geometry": {
                        "type": "LineString",
                        "coordinates": data['coords']
                    }
                }
                features.append(feat)

    print(f"Generated {len(features)} GeoJSON features.")
    
    # 5. Create Map
    # Center on Hyderabad roughly (or mean of all points)
    m = folium.Map(location=[17.4, 78.5], zoom_start=11, prefer_canvas=True)
    
    # Create GeoJSON Layer
    geojson_layer = folium.GeoJson(
        {"type": "FeatureCollection", "features": features},
        style_function=lambda x: {
            'color': x['properties']['color'],
            'weight': 3,
            'opacity': 0.6
        },
        tooltip=folium.GeoJsonTooltip(
            fields=['search_key', 'details', 'stops'],
            aliases=['Route:', 'Path:', 'Stops:'],
            sticky=False
        ),
        name="Bus Network"
    ).add_to(m)
    
    # Add Search Control
    Search(
        layer=geojson_layer,
        geom_type='LineString',
        placeholder='Search for a bus route (e.g. 219)',
        collapsed=False,
        search_label='search_key', # The property to search
        weight=5
    ).add_to(m)
    
    folium.LayerControl().add_to(m)
    
    m.save('network_map.html')
    print("Saved network_map.html")

if __name__ == "__main__":
    dfs = load_data()
    create_network_map(dfs)
