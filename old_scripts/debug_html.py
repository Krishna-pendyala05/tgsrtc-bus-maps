import requests
from bs4 import BeautifulSoup

url = 'https://hyderabadcitybus.in/route-no/44x/'
r = requests.get(url)
soup = BeautifulSoup(r.text, 'html.parser')

# Find all tables
tables = soup.find_all('table')
print(f'Found {len(tables)} tables')
for i, t in enumerate(tables):
    cls = t.get('class', [])
    print(f'  Table {i}: class={cls}')
    # Show first few rows
    rows = t.find_all('tr')[:3]
    for row in rows:
        print(f'    Row: {row.get_text(strip=True)[:80]}')

# Look for any div with route-related id
divs = soup.find_all('div', id=lambda x: x and 'route' in str(x).lower())
print(f'\nFound {len(divs)} divs with route in id')
for d in divs:
    print(f'  id={d.get("id")}')
