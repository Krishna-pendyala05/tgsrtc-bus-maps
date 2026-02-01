#!/usr/bin/env python3
"""
TGSRTC GTFS Analyzer - Unified CLI
===================================
Interactive maps and tools for exploring TGSRTC bus routes in Hyderabad.

Usage:
    python main.py generate [--all | --interactive | --trip-planner | --nearby | --network]
    python main.py deploy   # Copy outputs to web/
    python main.py info     # Show dataset info

Examples:
    python main.py generate --all
    python main.py generate --interactive --trip-planner
    python main.py deploy
"""

import argparse
import shutil
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def print_header(title: str) -> None:
    """Print a styled header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def cmd_generate(args) -> None:
    """Generate visualization files."""
    from src.data.gtfs_loader import GTFSLoader
    from src.generators import (
        InteractiveMapGenerator,
        TripPlannerGenerator,
        NearbyStopsGenerator,
        NetworkMapGenerator
    )
    from src.config import OUTPUT_DIR
    
    print_header("TGSRTC GTFS Map Generator")
    
    # Create shared loader
    print("\n📦 Loading GTFS data...")
    loader = GTFSLoader()
    
    # Determine which generators to run
    generators = []
    
    if args.all or args.interactive:
        generators.append(('Interactive Map', InteractiveMapGenerator(loader)))
    if args.all or args.trip_planner:
        generators.append(('Trip Planner', TripPlannerGenerator(loader)))
    if args.all or args.nearby:
        generators.append(('Nearby Stops', NearbyStopsGenerator(loader)))
    if args.all or args.network:
        generators.append(('Network Map', NetworkMapGenerator(loader)))
    
    if not generators:
        print("No generators selected. Use --all or specify individual generators.")
        print("  --all           Generate all visualizations")
        print("  --interactive   Generate interactive route map")
        print("  --trip-planner  Generate trip planner")
        print("  --nearby        Generate nearby stops finder")
        print("  --network       Generate full network map")
        return
    
    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Run generators
    for name, generator in generators:
        print(f"\n🔧 Generating {name}...")
        output_path = generator.save()
        file_size = output_path.stat().st_size / (1024 * 1024)
        print(f"   ✅ Saved: {output_path.name} ({file_size:.2f} MB)")
    
    print_header("COMPLETE!")
    print(f"\nOutput files saved to: {OUTPUT_DIR}")


def cmd_deploy(args) -> None:
    """Copy outputs to web directory for deployment."""
    from src.config import OUTPUT_DIR, WEB_DIR
    
    print_header("Deploying to Web Directory")
    
    # Files to deploy
    files_to_copy = [
        'interactive_map.html',
        'trip_planner.html',
        'nearby_stops.html',
        'network_map.html'
    ]
    
    # Ensure web dir exists
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    
    # Copy files
    copied = 0
    for filename in files_to_copy:
        src = OUTPUT_DIR / filename
        dst = WEB_DIR / filename
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  ✅ Copied: {filename}")
            copied += 1
        else:
            print(f"  ⚠️  Missing: {filename}")
    
    # Check for index.html
    index_file = WEB_DIR / 'index.html'
    if not index_file.exists():
        print("\n  📝 Creating index.html...")
        create_index_html(index_file)
    
    print_header("DEPLOY COMPLETE")
    print(f"\nDeployed {copied} files to: {WEB_DIR}")


def create_index_html(output_path: Path) -> None:
    """Create a landing page for the web directory."""
    html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TGSRTC Bus Maps - Hyderabad</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', system-ui, sans-serif;
            background: #0a0a0f;
            min-height: 100vh;
            color: #fff;
        }
        .bg-gradient {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: 
                radial-gradient(ellipse at 20% 20%, rgba(255, 0, 128, 0.15) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 80%, rgba(0, 255, 255, 0.15) 0%, transparent 50%);
            z-index: -1;
        }
        .container { max-width: 1000px; margin: 0 auto; padding: 50px 20px; }
        .header { text-align: center; margin-bottom: 60px; }
        .header h1 {
            font-size: 3rem;
            background: linear-gradient(135deg, #ff0080 0%, #00ffff 50%, #7c3aed 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .header p { color: #a1a1aa; font-size: 1.2rem; margin-top: 10px; }
        .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; }
        .card {
            background: rgba(20, 20, 30, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 28px;
            text-decoration: none;
            color: inherit;
            transition: all 0.3s;
        }
        .card:hover {
            transform: translateY(-5px);
            border-color: var(--accent);
            box-shadow: 0 20px 40px -12px rgba(0, 0, 0, 0.4);
        }
        .card:nth-child(1) { --accent: #ff0080; }
        .card:nth-child(2) { --accent: #00ffff; }
        .card:nth-child(3) { --accent: #ffff00; }
        .card:nth-child(4) { --accent: #00ff88; }
        .card-icon { font-size: 2.5rem; margin-bottom: 16px; }
        .card h2 { font-size: 1.4rem; margin-bottom: 10px; }
        .card p { color: #a1a1aa; font-size: 0.95rem; line-height: 1.5; }
    </style>
</head>
<body>
    <div class="bg-gradient"></div>
    <div class="container">
        <div class="header">
            <h1>🚌 TGSRTC Bus Maps</h1>
            <p>Interactive maps for Hyderabad city buses</p>
        </div>
        <div class="cards">
            <a href="trip_planner.html" class="card">
                <div class="card-icon">🗺️</div>
                <h2>Trip Planner</h2>
                <p>Plan your journey between any two locations. Find direct routes and transfers.</p>
            </a>
            <a href="interactive_map.html" class="card">
                <div class="card-icon">🔍</div>
                <h2>Route Search</h2>
                <p>Search for specific bus routes and see them highlighted on the map.</p>
            </a>
            <a href="nearby_stops.html" class="card">
                <div class="card-icon">📍</div>
                <h2>Stops Near Me</h2>
                <p>Find the nearest bus stops using your device's GPS location.</p>
            </a>
            <a href="network_map.html" class="card">
                <div class="card-icon">🌐</div>
                <h2>Full Network</h2>
                <p>Visualize the complete TGSRTC bus network with all routes.</p>
            </a>
        </div>
    </div>
</body>
</html>'''
    output_path.write_text(html, encoding='utf-8')


def cmd_info(args) -> None:
    """Show dataset information."""
    from src.data.gtfs_loader import GTFSLoader
    from src.config import DATA_DIR
    
    print_header("GTFS Dataset Info")
    
    print(f"\n📁 Data directory: {DATA_DIR}")
    
    loader = GTFSLoader()
    
    print("\n📊 Table sizes:")
    print(f"   Stops:      {len(loader.stops):,} rows")
    print(f"   Routes:     {len(loader.routes):,} rows")
    print(f"   Trips:      {len(loader.trips):,} rows")
    print(f"   Stop Times: {len(loader.stop_times):,} rows")
    
    # Show sample route names
    routes = loader.routes
    route_col = 'route_short_name' if 'route_short_name' in routes.columns else 'route_long_name'
    sample_routes = routes[route_col].head(10).tolist()
    
    print(f"\n🚌 Sample routes: {', '.join(str(r) for r in sample_routes)}...")


def cmd_serve(args) -> None:
    """Serve the web directory locally."""
    import http.server
    import socketserver
    import webbrowser
    from src.config import WEB_DIR
    import os
    
    PORT = args.port
    
    # Change to web directory
    os.chdir(WEB_DIR)
    
    Handler = http.server.SimpleHTTPRequestHandler
    
    # Allow address reuse
    socketserver.TCPServer.allow_reuse_address = True
    
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        url = f"http://127.0.0.1:{PORT}"
        print_header("Starting Local Server")
        print(f"  🚀 Server running at: {url}")
        print(f"  📂 Serving directory: {WEB_DIR}")
        print("  ⌨️  Press Ctrl+C to stop")
        
        # Try to open browser
        try:
            webbrowser.open(url)
        except:
            pass
            
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n  🛑 Server stopped.")


def main():
    parser = argparse.ArgumentParser(
        description='TGSRTC GTFS Analyzer - Generate interactive bus maps',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Generate command
    gen_parser = subparsers.add_parser('generate', help='Generate visualization files')
    gen_parser.add_argument('--all', action='store_true', help='Generate all visualizations')
    gen_parser.add_argument('--interactive', action='store_true', help='Generate interactive route map')
    gen_parser.add_argument('--trip-planner', action='store_true', help='Generate trip planner')
    gen_parser.add_argument('--nearby', action='store_true', help='Generate nearby stops finder')
    gen_parser.add_argument('--network', action='store_true', help='Generate full network map')
    gen_parser.set_defaults(func=cmd_generate)
    
    # Deploy command
    deploy_parser = subparsers.add_parser('deploy', help='Copy outputs to web directory')
    deploy_parser.set_defaults(func=cmd_deploy)
    
    # Serve command
    serve_parser = subparsers.add_parser('serve', help='Serve the web directory locally')
    serve_parser.add_argument('--port', type=int, default=8000, help='Port to serve on (default: 8000)')
    serve_parser.set_defaults(func=cmd_serve)
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show dataset information')
    info_parser.set_defaults(func=cmd_info)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == '__main__':
    main()
