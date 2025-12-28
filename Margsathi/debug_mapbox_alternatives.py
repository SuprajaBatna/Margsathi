import asyncio
import os
import sys
import httpx
from dotenv import load_dotenv

load_dotenv()

async def debug_alternatives():
    api_key = os.getenv("MAPBOX_API_KEY")
    if not api_key:
        print("No API key found")
        return

    # Koramangala to Indiranagar
    start_lat, start_lon = 12.9352, 77.6245
    end_lat, end_lon = 12.9718, 77.6412
    # Event point
    avoid_lat, avoid_lon = 12.9407, 77.6285

    async with httpx.AsyncClient() as client:
        # 1. Baseline
        url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{start_lon},{start_lat};{end_lon},{end_lat}"
        resp = await client.get(url, params={"access_token": api_key, "geometries": "geojson"})
        base_data = resp.json()
        base_dist = base_data['routes'][0]['distance']
        print(f"Baseline Distance: {base_dist}m")

        # 2. Waypoint Nudge
        nudge_lat, nudge_lon = avoid_lat + 0.008, avoid_lon + 0.008 # Shift ~1km
        nudge_url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{start_lon},{start_lat};{nudge_lon},{nudge_lat};{end_lon},{end_lat}"
        
        print(f"Testing Nudge via ({nudge_lat}, {nudge_lon})")
        resp = await client.get(nudge_url, params={"access_token": api_key, "geometries": "geojson"})
        data = resp.json()
        if 'routes' in data:
            r = data['routes'][0]
            print(f"Nudge Distance: {r['distance']}m, Duration: {r['duration']}s")
            if abs(r['distance'] - base_dist) > 100:
                print("SUCCESS: Path changed significantly!")
        else:
            print("Nudge Error:", data)

if __name__ == "__main__":
    asyncio.run(debug_alternatives())
