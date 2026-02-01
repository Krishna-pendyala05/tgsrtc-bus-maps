
import pandas as pd
import folium
from folium.plugins import MarkerCluster
import os
import matplotlib.pyplot as plt

DATA_DIR = '.'
files = {
    'stops': 'stops.txt',
    'stop_times': 'stop_times.txt',
    'trips': 'trips.txt'
}

dfs = {}

print("Loading data...")
for name, filename in files.items():
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        print(f"Loading {name}...")
        dtype_dict = {'trip_id': str, 'route_id': str, 'stop_id': str}
        # Read only necessary columns for quick check if file is huge
        dfs[name] = pd.read_csv(path, dtype=dtype_dict)
        print(f"  {name}: {dfs[name].shape}")

# Data Cleaning
def convert_gtfs_time(time_str):
    if pd.isna(time_str): return None
    try:
        h, m, s = map(int, time_str.split(':'))
        return h + m/60 + s/3600 # Convert to float hours for easier plotting
    except:
        return None

if 'stop_times' in dfs:
    print("Processing stop_times...")
    # Sample if too big for quick test, but user has 1.2M which is manageable
    st = dfs['stop_times']
    st['arrival_hour'] = st['arrival_time'].apply(lambda x: int(x.split(':')[0]) if isinstance(x, str) else 0)
    
    # Histogram of arrival hours
    print("Generating Trip Frequency Histogram...")
    plt.figure(figsize=(10, 6))
    st['arrival_hour'].hist(bins=range(0, 30), edgecolor='black')
    plt.title('Stop Arrivals by Hour of Day')
    plt.xlabel('Hour (GTFS time, can be > 24)')
    plt.ylabel('Frequency')
    plt.savefig('trip_frequency.png')
    print("Saved trip_frequency.png")

if 'stops' in dfs:
    print("Generating Stops Map...")
    stops = dfs['stops'].dropna(subset=['stop_lat', 'stop_lon'])
    mean_lat = stops['stop_lat'].mean()
    mean_lon = stops['stop_lon'].mean()
    
    m = folium.Map(location=[mean_lat, mean_lon], zoom_start=11)
    marker_cluster = MarkerCluster().add_to(m)
    
    # Limit map markers if way too many for performance, but 10k is fine for Cluster
    for idx, row in stops.iterrows():
        folium.CircleMarker(
            location=[row['stop_lat'], row['stop_lon']],
            radius=3,
            color='blue',
            fill=True,
            popup=row['stop_name']
        ).add_to(marker_cluster)
        
    m.save('stops_map.html')
    print("Saved stops_map.html")
