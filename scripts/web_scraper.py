"""
TGSRTC Web Scraper - hyderabadcitybus.in (v2 - Fixed)
======================================================
Scrapes accurate route and stop data from the website.

Outputs:
- scraped_routes.json: All routes with ordered stops
- scraped_routes_summary.csv: Quick comparison data
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from pathlib import Path
from datetime import datetime

# Configuration
BASE_URL = "https://hyderabadcitybus.in"
OUTPUT_DIR = Path(".")
DELAY_BETWEEN_REQUESTS = 0.8  # Slightly faster but still polite

# Headers to look like a real browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}

def get_page(url: str) -> BeautifulSoup:
    """Fetch a page and return BeautifulSoup object"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}")
        return None

def get_all_route_urls() -> list:
    """Collect all route URLs from paginated home page"""
    print("=" * 60)
    print("PHASE 1: Collecting Route URLs")
    print("=" * 60)
    
    # Check if we already have URLs saved
    urls_file = OUTPUT_DIR / 'route_urls.json'
    if urls_file.exists():
        with open(urls_file, 'r') as f:
            route_urls = json.load(f)
        print(f"  Loaded {len(route_urls)} URLs from cache")
        return route_urls
    
    route_urls = []
    page_num = 1
    
    while True:
        if page_num == 1:
            url = BASE_URL
        else:
            url = f"{BASE_URL}/page/{page_num}/"
        
        print(f"  Scanning page {page_num}...", end=" ", flush=True)
        soup = get_page(url)
        
        if not soup:
            break
        
        # Find all route links
        links = soup.find_all('a', href=re.compile(r'/route-no/[^/]+/$'))
        
        new_routes = []
        for link in links:
            href = link.get('href')
            if href:
                full_url = href if href.startswith('http') else BASE_URL + href
                if full_url not in route_urls:
                    route_urls.append(full_url)
                    new_routes.append(full_url)
        
        print(f"found {len(new_routes)} routes")
        
        if len(new_routes) == 0:
            break
        
        page_num += 1
        time.sleep(DELAY_BETWEEN_REQUESTS)
        
        if page_num > 100:
            break
    
    # Save URLs
    with open(urls_file, 'w') as f:
        json.dump(route_urls, f, indent=2)
    
    print(f"\n  Total routes found: {len(route_urls)}")
    return route_urls

def parse_route_page(url: str) -> dict:
    """Extract route details from a single route page"""
    soup = get_page(url)
    if not soup:
        return None
    
    route_data = {
        'url': url,
        'route_number': None,
        'origin': None,
        'destination': None,
        'onwards_stops': [],
        'return_stops': [],
        'first_bus_onwards': None,
        'last_bus_onwards': None,
        'first_bus_return': None,
        'last_bus_return': None,
    }
    
    # Get route number from title (h1 with class wp-block-post-title)
    title = soup.find('h1', class_='wp-block-post-title')
    if title:
        route_data['route_number'] = title.get_text(strip=True)
    
    # Get origin/destination from description
    paragraphs = soup.find_all('p')
    for p in paragraphs:
        text = p.get_text()
        match = re.search(r'runs between (.+?) and (.+?)\.', text)
        if match:
            route_data['origin'] = match.group(1).strip()
            route_data['destination'] = match.group(2).strip()
            break
    
    # Get the overview table for timings
    overview_table = soup.find('table', class_='select-your-route')
    if overview_table:
        rows = overview_table.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).lower()
                if 'first bus' in label:
                    route_data['first_bus_onwards'] = cells[1].get_text(strip=True) if len(cells) > 1 else None
                    route_data['first_bus_return'] = cells[2].get_text(strip=True) if len(cells) > 2 else None
                elif 'last bus' in label:
                    route_data['last_bus_onwards'] = cells[1].get_text(strip=True) if len(cells) > 1 else None
                    route_data['last_bus_return'] = cells[2].get_text(strip=True) if len(cells) > 2 else None
    
    # Get stops from the route tables
    # The stops tables are INSIDE divs with id 'onwards-route' and 'return-route'
    
    # Onwards route stops
    onwards_div = soup.find('div', id='onwards-route')
    if onwards_div:
        table = onwards_div.find('table')
        if table:
            stops = []
            rows = table.find_all('tr')
            for row in rows[1:]:  # Skip header row
                cells = row.find_all('td')
                if len(cells) >= 2:
                    # Column 2 is the stop name (index 1)
                    stop_name = cells[1].get_text(strip=True)
                    if stop_name:
                        stops.append(stop_name)
            route_data['onwards_stops'] = stops
    
    # Return route stops
    return_div = soup.find('div', id='return-route')
    if return_div:
        table = return_div.find('table')
        if table:
            stops = []
            rows = table.find_all('tr')
            for row in rows[1:]:  # Skip header row
                cells = row.find_all('td')
                if len(cells) >= 2:
                    stop_name = cells[1].get_text(strip=True)
                    if stop_name:
                        stops.append(stop_name)
            route_data['return_stops'] = stops
    
    # Fallback: if no stops found in divs, try all tables
    if not route_data['onwards_stops'] and not route_data['return_stops']:
        tables = soup.find_all('table')
        for i, table in enumerate(tables):
            if table.get('class') == ['select-your-route']:
                continue  # Skip overview table
            
            stops = []
            rows = table.find_all('tr')
            for row in rows[1:]:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    stop_name = cells[1].get_text(strip=True)
                    if stop_name and 'bus stop' not in stop_name.lower()[:15]:
                        stops.append(stop_name)
            
            if stops:
                if not route_data['onwards_stops']:
                    route_data['onwards_stops'] = stops
                elif not route_data['return_stops']:
                    route_data['return_stops'] = stops
    
    return route_data

def scrape_all_routes(route_urls: list) -> list:
    """Scrape details from all route pages"""
    print("\n" + "=" * 60)
    print("PHASE 2: Scraping Route Details")
    print("=" * 60)
    
    all_routes = []
    total = len(route_urls)
    
    for i, url in enumerate(route_urls, 1):
        route_id = url.split('/route-no/')[-1].rstrip('/')
        print(f"  [{i}/{total}] {route_id}", end=" ", flush=True)
        
        route_data = parse_route_page(url)
        
        if route_data:
            stops_count = len(route_data['onwards_stops']) + len(route_data['return_stops'])
            print(f"✓ ({len(route_data['onwards_stops'])}+{len(route_data['return_stops'])} stops)")
            all_routes.append(route_data)
        else:
            print("✗")
        
        time.sleep(DELAY_BETWEEN_REQUESTS)
        
        # Save progress every 100 routes
        if i % 100 == 0:
            save_results(all_routes, progress=True)
            print(f"  💾 Progress saved ({i} routes)")
    
    return all_routes

def save_results(routes: list, progress=False):
    """Save results to files"""
    suffix = '_progress' if progress else ''
    
    # Save full data as JSON
    with open(OUTPUT_DIR / f'scraped_routes{suffix}.json', 'w', encoding='utf-8') as f:
        json.dump({
            'scraped_at': datetime.now().isoformat(),
            'source': BASE_URL,
            'total_routes': len(routes),
            'routes': routes
        }, f, ensure_ascii=False, indent=2)
    
    if not progress:
        # Save CSV summary
        import csv
        with open(OUTPUT_DIR / 'scraped_routes_summary.csv', 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['route_number', 'origin', 'destination', 'onwards_count', 'return_count', 'first_stop', 'last_stop', 'first_bus', 'last_bus'])
            for r in routes:
                onwards = r.get('onwards_stops', [])
                writer.writerow([
                    r.get('route_number', ''),
                    r.get('origin', ''),
                    r.get('destination', ''),
                    len(onwards),
                    len(r.get('return_stops', [])),
                    onwards[0] if onwards else '',
                    onwards[-1] if onwards else '',
                    r.get('first_bus_onwards', ''),
                    r.get('last_bus_onwards', '')
                ])

def main():
    print("\n" + "=" * 60)
    print("TGSRTC WEB SCRAPER v2")
    print("=" * 60)
    
    # Phase 1: Get all route URLs
    route_urls = get_all_route_urls()
    
    # Phase 2: Scrape each route
    routes = scrape_all_routes(route_urls)
    
    # Phase 3: Save final results
    print("\n" + "=" * 60)
    print("PHASE 3: Saving Results")
    print("=" * 60)
    save_results(routes)
    
    # Statistics
    total_onwards = sum(len(r.get('onwards_stops', [])) for r in routes)
    total_return = sum(len(r.get('return_stops', [])) for r in routes)
    
    print(f"\n  📊 Final Statistics:")
    print(f"     Routes: {len(routes)}")
    print(f"     Onwards stops: {total_onwards}")
    print(f"     Return stops: {total_return}")
    print(f"\n  📁 Files saved:")
    print(f"     - scraped_routes.json")
    print(f"     - scraped_routes_summary.csv")
    
    print("\n" + "=" * 60)
    print("COMPLETE!")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
