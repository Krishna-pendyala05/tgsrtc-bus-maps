import pandas as pd

st = pd.read_csv('stop_times.txt', dtype=str)
stops = pd.read_csv('stops.txt', dtype=str)

trip_stops = st[st['trip_id'] == '41773998'].copy()
trip_stops['stop_sequence'] = pd.to_numeric(trip_stops['stop_sequence'])
trip_stops = trip_stops.sort_values('stop_sequence')
merged = trip_stops.merge(stops, on='stop_id')

print("44X STOPS from GTFS (trip 41773998):")
print("-" * 50)
for i, r in merged.iterrows():
    print(f"{int(r['stop_sequence']):2d}. {r['stop_name']}")

print("\n\nExpected stops from official website:")
print("-" * 50)
expected = [
    "Secunderabad Railway Station",
    "Rathifile Bus Station", 
    "Chilkalguda",
    "Parsigutta",
    "Padmarao Nagar",
    "Skandagiri",
    "Srinivas Nagar",
    "Sunnam Batti",
    "Gangaputhra Colony"
]
for i, stop in enumerate(expected, 1):
    print(f"{i}. {stop}")
