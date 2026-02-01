# TGSRTC GTFS Analyzer

Interactive maps and analysis tools for TGSRTC (Telangana State Road Transport Corporation) bus routes in Hyderabad.

## Features

- **Trip Planner** - Plan journeys between any two locations with direct routes and transfers
- **Route Search** - Interactive map to search and visualize specific bus routes
- **Nearby Stops** - GPS-based finder for the nearest bus stops
- **Network Map** - Full network visualization with all routes

## Installation

1. Clone or download this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Generate All Visualizations

```bash
python main.py generate --all
```

### Generate Specific Tools

```bash
python main.py generate --interactive      # Route search map
python main.py generate --trip-planner     # Trip planner
python main.py generate --nearby           # Nearby stops finder
python main.py generate --network          # Full network map
```

### Deploy to GitHub Pages

1. Run the deploy command to populate the `web/` directory:

   ```bash
   python main.py deploy
   ```

2. Go to your GitHub repository settings:
   - Go to **Settings** > **Pages**
   - Under **Source**, select **Deploy from branch**
   - Under **Branch**, select `main` (or `master`) and set the folder to `/web` (if enabled) or push the contents of `web/` to a `gh-pages` branch.

   _Note: If you cannot select `/web` as a source folder, you may need to configure a GitHub Actions workflow or simply push the contents of the `web/` folder to the root of a `gh-pages` branch._

### Show Dataset Info

```bash
python main.py info
```

## Project Structure

```
├── main.py              # Unified CLI entry point
├── requirements.txt     # Python dependencies
├── data/               # GTFS data files (txt)
├── src/                # Source code
│   ├── config.py       # Configuration constants
│   ├── data/           # Data loading module
│   │   └── gtfs_loader.py
│   ├── utils/          # Utility functions
│   │   ├── geo.py      # Geographic calculations
│   │   └── html_builder.py
│   └── generators/     # Visualization generators
│       ├── base.py
│       ├── interactive_map.py
│       ├── trip_planner.py
│       ├── nearby_stops.py
│       └── network_map.py
├── outputs/            # Generated HTML files
├── web/                # Deployment directory
├── cache/              # Scraped data cache
└── scripts/            # Utility scripts
```

## Data Source

This project uses GTFS (General Transit Feed Specification) data from TGSRTC.
The data includes stops, routes, trips, and schedules for Hyderabad city buses.

## Technology

- **Python** with pandas for data processing
- **Leaflet.js** for interactive maps
- **Self-contained HTML** files with embedded data for easy deployment

## License

This project is for educational and informational purposes.
GTFS data is sourced from public transit data feeds.
