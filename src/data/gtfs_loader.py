"""
GTFS Data Loader
================
Unified GTFS data loading with lazy loading and caching.
Eliminates code duplication across all generator modules.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Optional, List, Union
import logging

from ..config import DATA_DIR, GTFS_FILES, GTFS_DTYPES

logger = logging.getLogger(__name__)


class GTFSLoader:
    """
    Unified GTFS data loader with lazy loading and caching.
    
    Usage:
        loader = GTFSLoader()
        
        # Access individual tables as properties (lazy loaded)
        stops = loader.stops
        routes = loader.routes
        
        # Or load specific tables explicitly
        data = loader.load('stops', 'routes', 'trips')
        
        # Load all tables
        all_data = loader.load_all()
    """
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize the GTFS loader.
        
        Args:
            data_dir: Path to directory containing GTFS txt files.
                      Defaults to project's data/ directory.
        """
        self.data_dir = Path(data_dir) if data_dir else DATA_DIR
        self._cache: Dict[str, pd.DataFrame] = {}
        self._validate_data_dir()
    
    def _validate_data_dir(self) -> None:
        """Check if data directory exists and has required files."""
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Data directory not found: {self.data_dir}")
        
        # Check for minimum required files
        required = ['stops.txt', 'routes.txt', 'trips.txt', 'stop_times.txt']
        missing = [f for f in required if not (self.data_dir / f).exists()]
        if missing:
            logger.warning(f"Missing GTFS files: {missing}")
    
    def _load_table(self, table_name: str) -> pd.DataFrame:
        """
        Load a single GTFS table from disk.
        
        Args:
            table_name: Name of the table (e.g., 'stops', 'routes')
            
        Returns:
            DataFrame with the table data
        """
        if table_name in self._cache:
            return self._cache[table_name]
        
        filename = GTFS_FILES.get(table_name, f"{table_name}.txt")
        filepath = self.data_dir / filename
        
        if not filepath.exists():
            raise FileNotFoundError(f"GTFS file not found: {filepath}")
        
        logger.info(f"Loading {table_name} from {filepath}")
        
        # Build dtype dict for this file
        dtype_dict = {k: v for k, v in GTFS_DTYPES.items()}
        
        # Load the file
        df = pd.read_csv(filepath, dtype=dtype_dict, low_memory=False)
        logger.info(f"  Loaded {table_name}: {df.shape[0]:,} rows, {df.shape[1]} columns")
        
        # Cache it
        self._cache[table_name] = df
        return df
    
    def load(self, *tables: str) -> Dict[str, pd.DataFrame]:
        """
        Load multiple GTFS tables.
        
        Args:
            *tables: Names of tables to load (e.g., 'stops', 'routes')
            
        Returns:
            Dictionary mapping table names to DataFrames
        """
        result = {}
        for table in tables:
            try:
                result[table] = self._load_table(table)
            except FileNotFoundError as e:
                logger.warning(str(e))
        return result
    
    def load_all(self) -> Dict[str, pd.DataFrame]:
        """Load all available GTFS tables."""
        return self.load(*GTFS_FILES.keys())
    
    def clear_cache(self) -> None:
        """Clear the internal cache to free memory."""
        self._cache.clear()
        logger.info("Cache cleared")
    
    # ========================================================================
    # LAZY PROPERTIES - Access individual tables
    # ========================================================================
    
    @property
    def stops(self) -> pd.DataFrame:
        """Bus stops with coordinates and names."""
        return self._load_table('stops')
    
    @property
    def routes(self) -> pd.DataFrame:
        """Bus route definitions."""
        return self._load_table('routes')
    
    @property
    def trips(self) -> pd.DataFrame:
        """Individual bus trips for each route."""
        return self._load_table('trips')
    
    @property
    def stop_times(self) -> pd.DataFrame:
        """Stop arrival/departure times for each trip."""
        return self._load_table('stop_times')
    
    @property
    def calendar(self) -> pd.DataFrame:
        """Service calendar (days of operation)."""
        return self._load_table('calendar')
    
    @property
    def agency(self) -> pd.DataFrame:
        """Transit agency information."""
        return self._load_table('agency')
    
    # ========================================================================
    # DERIVED DATA METHODS
    # ========================================================================
    
    def get_route_name(self, route_id: str) -> str:
        """Get the display name for a route."""
        routes = self.routes
        match = routes[routes['route_id'] == route_id]
        if match.empty:
            return route_id
        row = match.iloc[0]
        return str(row.get('route_short_name', row.get('route_long_name', route_id)))
    
    def get_stops_for_trip(self, trip_id: str) -> pd.DataFrame:
        """
        Get all stops for a trip in order.
        
        Returns DataFrame with stop details sorted by stop_sequence.
        """
        stop_times = self.stop_times
        stops = self.stops
        
        trip_stops = stop_times[stop_times['trip_id'] == trip_id].copy()
        trip_stops['stop_sequence'] = pd.to_numeric(trip_stops['stop_sequence'])
        trip_stops = trip_stops.sort_values('stop_sequence')
        
        # Merge with stop details
        return trip_stops.merge(stops, on='stop_id', how='left')
    
    def get_representative_trips(self) -> pd.DataFrame:
        """
        Get representative trips for each route+direction.
        
        The representative trip is the one with the most stops,
        which typically represents the main trunk route.
        """
        stop_times = self.stop_times
        trips = self.trips
        
        # Count stops per trip
        trip_counts = stop_times.groupby('trip_id').size().reset_index(name='stop_count')
        
        # Merge with trips
        trips_enriched = trips.merge(trip_counts, on='trip_id')
        
        # Fill missing direction_id
        if 'direction_id' not in trips_enriched.columns:
            trips_enriched['direction_id'] = '0'
        trips_enriched['direction_id'] = trips_enriched['direction_id'].fillna('0')
        
        # Get trip with most stops per route+direction
        rep_trips = (trips_enriched
                     .sort_values('stop_count', ascending=False)
                     .drop_duplicates(['route_id', 'direction_id']))
        
        logger.info(f"Found {len(rep_trips)} representative trips")
        return rep_trips
    
    def get_routes_at_stop(self, stop_id: str) -> List[str]:
        """Get list of route names serving a specific stop."""
        stop_times = self.stop_times
        trips = self.trips
        routes = self.routes
        
        # Get trips that visit this stop
        trip_ids = stop_times[stop_times['stop_id'] == stop_id]['trip_id'].unique()
        
        # Get route IDs for these trips
        route_ids = trips[trips['trip_id'].isin(trip_ids)]['route_id'].unique()
        
        # Get route names
        route_name_col = 'route_short_name' if 'route_short_name' in routes.columns else 'route_long_name'
        route_names = routes[routes['route_id'].isin(route_ids)][route_name_col].unique()
        
        return sorted([str(n) for n in route_names])
    
    def build_stop_routes_map(self) -> Dict[str, List[str]]:
        """
        Build a mapping of stop_id -> list of route names.
        
        This is used by the nearby stops finder.
        """
        from collections import defaultdict
        
        stop_times = self.stop_times
        trips = self.trips
        routes = self.routes
        
        # Merge trips with routes to get route names
        route_name_col = 'route_short_name' if 'route_short_name' in routes.columns else 'route_long_name'
        trips_routes = trips[['trip_id', 'route_id']].merge(
            routes[['route_id', route_name_col]], on='route_id', how='left'
        )
        
        # Merge with stop_times
        merged = stop_times[['stop_id', 'trip_id']].merge(trips_routes, on='trip_id', how='left')
        
        # Group by stop
        stop_routes = defaultdict(set)
        for _, row in merged.iterrows():
            if pd.notna(row[route_name_col]):
                stop_routes[row['stop_id']].add(str(row[route_name_col]))
        
        # Convert to sorted lists
        return {k: sorted(list(v)) for k, v in stop_routes.items()}
