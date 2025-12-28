import asyncio
import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv()

async def debug_mapbox():
    api_key = os.getenv("MAPBOX_API_KEY")
    if not api_key:
        print("No API key found")
        return

    # Koramangala to Indiranagar
    start_lat, start_lon = 12.9352, 77.6245
    end_lat, end_lon = 12.9718, 77.6412
    # A point specifically on the main road (Sarjapur Road / Intermediate Ring Road intersection area)
    # This point is very likely on the baseline
    avoid_lat, avoid_lon = 12.9407, 77.6285

    base_url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{start_lon},{start_lat};{end_lon},{end_lat}"
    
    print(f"Testing route from ({start_lat}, {start_lon}) to ({end_lat}, {end_lon})")
    print(f"Trying to avoid ({avoid_lat}, {avoid_lon})\n")

    async with httpx.AsyncClient() as client:
        # 1. Baseline
        resp = await client.get(base_url, params={"access_token": api_key, "geometries": "polyline6", "overview": "full"})
        base_data = resp.json()
        if 'routes' not in base_data:
            print("Baseline Error:", base_data)
            return
        base_dist = base_data['routes'][0]['distance']
        base_geom = base_data['routes'][0]['geometry']
        print(f"Baseline Distance: {base_dist}m, Geometry Hash: {hash(base_geom)}")

        # 2. Test common formats
        # Mapbox docs say: exclude=point(longitude latitude) or exclude=motorway,etc.
        test_params = [
            ("Space", f"point({avoid_lon} {avoid_lat})"),
            ("Comma", f"point({avoid_lon},{avoid_lat})"),
            ("Space+Radius", f"point({avoid_lon} {avoid_lat},500)"), # Some implementations use this
        ]

        for label, fmt in test_params:
            print(f"\n--- Testing format: [{label}] ({fmt}) ---")
            params = {
                "access_token": api_key,
                "geometries": "polyline6",
                "overview": "full",
                "exclude": fmt,
                "alternatives": "true"
            }
            resp = await client.get(base_url, params=params)
            data = resp.json()
            
            if 'routes' in data:
                print(f"Found {len(data['routes'])} routes.")
                for i, r in enumerate(data['routes']):
                    dist = r['distance']
                    geom = r['geometry']
                    is_diff = geom != base_geom
                    print(f"  Route {i}: {dist}m, Different: {is_diff}")
            else:
                print(f"  API Error: {data.get('message', 'Unknown error')}")

if __name__ == "__main__":
    asyncio.run(debug_mapbox())
