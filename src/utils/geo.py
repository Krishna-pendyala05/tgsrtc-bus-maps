"""
Geography and GeoJSON Utilities
================================
Shared utilities for coordinate calculations and GeoJSON feature creation.
"""

import math
from typing import List, Dict, Set, Tuple, Any


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth.
    
    Args:
        lat1, lon1: Coordinates of first point
        lat2, lon2: Coordinates of second point
        
    Returns:
        Distance in kilometers
    """
    R = 6371  # Earth's radius in km
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = (math.sin(delta_lat / 2) ** 2 + 
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def calculate_route_overlap(stops1: Set[str], stops2: Set[str]) -> float:
    """
    Calculate Jaccard similarity between two sets of stops.
    
    Used to determine if two route directions should be merged
    as a bidirectional route.
    
    Args:
        stops1: Set of stop IDs for direction 0
        stops2: Set of stop IDs for direction 1
        
    Returns:
        Jaccard similarity coefficient (0.0 to 1.0)
    """
    if not stops1 or not stops2:
        return 0.0
    
    intersection = len(stops1.intersection(stops2))
    union = len(stops1.union(stops2))
    
    return intersection / union if union > 0 else 0.0


def create_geojson_feature(
    coords: List[Tuple[float, float]], 
    properties: Dict[str, Any],
    geometry_type: str = "LineString"
) -> Dict[str, Any]:
    """
    Create a GeoJSON Feature.
    
    Args:
        coords: List of (longitude, latitude) tuples (note: GeoJSON uses lon, lat order)
        properties: Feature properties dict
        geometry_type: GeoJSON geometry type (default: "LineString")
        
    Returns:
        GeoJSON Feature dict
    """
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {
            "type": geometry_type,
            "coordinates": coords if geometry_type == "LineString" else [coords]
        }
    }


def create_geojson_collection(features: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create a GeoJSON FeatureCollection.
    
    Args:
        features: List of GeoJSON Feature dicts
        
    Returns:
        GeoJSON FeatureCollection dict
    """
    return {
        "type": "FeatureCollection",
        "features": features
    }


def coords_to_geojson(latlon_points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """
    Convert lat/lon points to GeoJSON lon/lat order.
    
    Args:
        latlon_points: List of (latitude, longitude) tuples
        
    Returns:
        List of (longitude, latitude) tuples for GeoJSON
    """
    return [(lon, lat) for lat, lon in latlon_points]


def get_bounds(coords: List[Tuple[float, float]]) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """
    Calculate bounding box for a set of coordinates.
    
    Args:
        coords: List of (lon, lat) tuples
        
    Returns:
        ((min_lon, min_lat), (max_lon, max_lat))
    """
    if not coords:
        return ((0, 0), (0, 0))
    
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    
    return ((min(lons), min(lats)), (max(lons), max(lats)))


def generate_color_for_route(route_name: str) -> str:
    """
    Generate a consistent color for a route based on its name.
    
    Args:
        route_name: Route identifier
        
    Returns:
        Hex color code
    """
    # Use a hash of the route name to pick from a predefined palette
    colors = [
        "#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00",
        "#ffff33", "#a65628", "#f781bf", "#999999", "#66c2a5",
        "#fc8d62", "#8da0cb", "#e78ac3", "#a6d854", "#ffd92f"
    ]
    
    hash_val = sum(ord(c) for c in str(route_name))
    return colors[hash_val % len(colors)]
