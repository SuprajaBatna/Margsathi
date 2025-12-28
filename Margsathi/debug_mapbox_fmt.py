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
    # Point on Sarjapur Road / Intermediate path
    avoid_lat, avoid_lon = 12.9407, 77.6285

    base_url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{start_lon},{start_lat};{end_lon},{end_lat}"
    
    formats = [
        ("Space (No Radius)", f"point({avoid_lon} {avoid_lat})"),
        ("Space (Radius 500)", f"point({avoid_lon} {avoid_lat},500)"),
        ("Space (Radius 1000)", f"point({avoid_lon} {avoid_lat},1000)"),
        ("Comma (No Radius)", f"point({avoid_lon},{avoid_lat})")
    ]

    async with httpx.AsyncClient() as client:
        # Baseline
        resp = await client.get(base_url, params={"access_token": api_key, "geometries": "polyline6"})
        base_dist = resp.json()['routes'][0]['distance']
        print(f"Baseline: {base_dist}m")

        for label, fmt in formats:
            params = {
                "access_token": api_key,
                "geometries": "polyline6",
                "exclude": fmt,
                "alternatives": "true"
            }
            resp = await client.get(base_url, params=params)
            data = resp.json()
            if 'routes' in data:
                dist = data['routes'][0]['distance']
                geom = data['routes'][0]['geometry']
                print(f"Format [{label}]: {dist}m, Exclusion: {fmt}")
                if dist != base_dist:
                    print(f"  SUCCESS: Found different route with {label}!")
                else:
                    print(f"  FAILURE: Same distance as baseline.")
            else:
                print(f"Format [{label}]: Error - {data.get('message')}")

if __name__ == "__main__":
    asyncio.run(debug_mapbox())
