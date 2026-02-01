
import pandas as pd
import folium
from folium.plugins import MarkerCluster
import os

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
            # Enforce string types for IDs to avoid mismatch errors
            dtype_dict = {
                'trip_id': str,
                'route_id': str, 
                'stop_id': str, 
                'service_id': str,
                'shape_id': str
            }
            dfs[name] = pd.read_csv(path, dtype=dtype_dict)
            print(f"  {name}: {dfs[name].shape}")
        else:
            print(f"WARNING: {filename} missing!")
    return dfs

def analyze_and_plot(dfs):
    stops = dfs.get('stops')
    stop_times = dfs.get('stop_times')
    trips = dfs.get('trips')
    routes = dfs.get('routes')

    if stops is None or stop_times is None or trips is None or routes is None:
        print("Missing critical files. Aborting.")
        return

    # 1. Map Stops to Routes
    # We want: Stop Name -> [Bus 219, Bus 10, ...]
    
    # Merge Trips -> Routes to get route_name for each trip
    print("Linking Trips to Routes...")
    # Use 'route_short_name' if available, else 'route_long_name'
    route_name_col = 'route_short_name' if 'route_short_name' in routes.columns else 'route_long_name'
    
    trips_routes = trips[['trip_id', 'route_id']].merge(
        routes[['route_id', route_name_col]], 
        on='route_id', 
        how='left'
    )
    
    # Merge StopTimes -> TripsRoutes to get route_name for each stop_time
    print("Linking Stop Times to Route Names (this might take a moment)...")
    # Optimize: We only need stop_id and trip_id from stop_times
    st_lite = stop_times[['stop_id', 'trip_id']]
    
    merged = st_lite.merge(trips_routes, on='trip_id', how='left')
    
    # Group by Stop ID and get unique route names
    print("Aggregating Routes per Stop...")
    stop_routes = merged.groupby('stop_id')[route_name_col].apply(lambda x: list(x.dropna().unique()))
    
    # Join back to stops
    stops_enhanced = stops.set_index('stop_id').join(stop_routes.rename('routes'))
    stops_enhanced = stops_enhanced.reset_index()
    
    # Data Cleaning: Drop stops with no lat/lon
    stops_enhanced = stops_enhanced.dropna(subset=['stop_lat', 'stop_lon'])
    print(f"Stops with valid locations: {len(stops_enhanced)}")

    # 2. Visualize
    mean_lat = stops_enhanced['stop_lat'].mean()
    mean_lon = stops_enhanced['stop_lon'].mean()
    m = folium.Map(location=[mean_lat, mean_lon], zoom_start=11)
    
    # Feature Groups for Layer Control
    stops_group = folium.FeatureGroup(name="All Stops")
    route_group = folium.FeatureGroup(name="Route 219")
    
    # Cluster for stops (add to stops_group)
    marker_cluster = MarkerCluster().add_to(stops_group)
    
    print("Adding stops to map...")
    for idx, row in stops_enhanced.iterrows():
        r_list = row['routes'] if isinstance(row['routes'], list) else []
        r_str = ", ".join(map(str, r_list[:10]))
        if len(r_list) > 10:
            r_str += "..."
            
        popup_text = f"<b>{row['stop_name']}</b><br>Routes: {r_str}"
        
        folium.CircleMarker(
            location=[row['stop_lat'], row['stop_lon']],
            radius=4,
            color='blue',
            fill=True,
            fill_opacity=0.6,
            popup=folium.Popup(popup_text, max_width=300)
        ).add_to(marker_cluster)

    # 3. Highlight Route 219
    target_route = "219"
    print(f"Visualizing Route {target_route} path...")
    
    r_matches = routes[routes[route_name_col].astype(str) == target_route]
    
    if not r_matches.empty:
        rid = r_matches.iloc[0]['route_id']
        route_trips = trips[trips['route_id'] == rid]
        if not route_trips.empty:
            sample_trip_id = route_trips.iloc[0]['trip_id']
            print(f"Using Trip ID {sample_trip_id} for path visualization")
            
            path_st = stop_times[stop_times['trip_id'] == sample_trip_id].sort_values('stop_sequence')
            path_geo = path_st.merge(stops, on='stop_id', how='left')
            points = path_geo[['stop_lat', 'stop_lon']].values.tolist()
            
            # Calculate Metadata
            start_stop = path_geo.iloc[0]['stop_name']
            end_stop = path_geo.iloc[-1]['stop_name']
            stop_count = len(path_geo)
            
            tooltip_text = f"Route: {target_route}<br>From: {start_stop}<br>To: {end_stop}<br>Stops: {stop_count}"
            
            # Draw Line (add to route_group)
            folium.PolyLine(
                points, 
                color="red", 
                weight=4, 
                opacity=0.8,
                tooltip=tooltip_text
            ).add_to(route_group)

            # Highlighting stops for this route (add to route_group)
            print(f"Adding {len(path_geo)} stops for Route {target_route}...")
            for idx, row in path_geo.iterrows():
                popup_text = f"<b>{row['stop_name']}</b><br>Route: {target_route}<br>Stop Seq: {row['stop_sequence']}"
                folium.CircleMarker(
                    location=[row['stop_lat'], row['stop_lon']],
                    radius=6,
                    color='red',
                    fill=True,
                    fill_color='red',
                    fill_opacity=1.0,
                    popup=folium.Popup(popup_text, max_width=300)
                ).add_to(route_group) 
                
        else:
            print("No trips found for this route.")
    else:
        print(f"Route {target_route} not found in routes file.")

    # Add Groups and Layer Control
    stops_group.add_to(m)
    route_group.add_to(m)
    folium.LayerControl().add_to(m)

    output_file = 'stops_map_enhanced.html'
    m.save(output_file)
    print(f"Saved {output_file}")

if __name__ == "__main__":
    dfs = load_data()
    analyze_and_plot(dfs)
