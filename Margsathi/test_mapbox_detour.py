import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from dotenv import load_dotenv
load_dotenv()

from backend.services.router_manager import router_manager
from backend.config import RoutingProvider

async def test_detour():
    # Koramangala to Indiranagar (approx)
    src_lat, src_lon = 12.9352, 77.6245
    dst_lat, dst_lon = 12.9718, 77.6412
    
    print("--- Fetching Baseline ---")
    baseline = await router_manager.get_route(src_lat, src_lon, dst_lat, dst_lon, preferred_provider=RoutingProvider.MAPBOX)
    if not baseline:
        print("Failed to fetch baseline")
        return
        
    base_geom = baseline['routes'][0]['geometry']
    base_dist = baseline['routes'][0]['distance']
    print(f"Baseline Distance: {base_dist}m")
    
    # Pick a point in the middle of the geometry
    # We'll just pick a coordinate that is likely on the path
    # For simplicity, let's use a known point near Sony World signal
    avoid_point = {"lat": 12.9407, "lon": 77.6285} 
    
    print(f"\n--- Fetching Detour (avoiding {avoid_point}) ---")
    detour = await router_manager.get_route(src_lat, src_lon, dst_lat, dst_lon, avoid_point=avoid_point, preferred_provider=RoutingProvider.MAPBOX)
    
    if not detour:
        print("Failed to fetch detour (Maybe Mapbox couldn't find an alternate?)")
        return
        
    detour_geom = detour['routes'][0]['geometry']
    detour_dist = detour['routes'][0]['distance']
    print(f"Detour Distance: {detour_dist}m")
    
    if base_geom == detour_geom:
        print("\nFAILURE: Geometries are identical! Mapbox ignored the exclusion or couldn't detour.")
    else:
        print("\nSUCCESS: Geometries are different!")
        print(f"Difference: {abs(detour_dist - base_dist)} meters")

if __name__ == "__main__":
    asyncio.run(test_detour())
