import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.services.h3_service import h3_service
import h3

def test_h3_logic():
    print("Testing H3 Spatial Logic...")
    
    # Coordinates in Bangalore
    # Koramangala 3rd Block
    lat, lon = 12.9352, 77.6245
    
    # 1. Test coordinate to hex
    hex_id = h3_service.latlng_to_hex(lat, lon)
    print(f"Coordinate ({lat}, {lon}) -> H3 Hex: {hex_id}")
    
    # 2. Test intersection
    route_hexes = {hex_id} # Mock route with one hex
    
    # Event exactly in the same hex
    print("\nCase 1: Event in same hex")
    relevant = h3_service.is_event_relevant(lat, lon, route_hexes)
    print(f"Relevant: {relevant} (Expected: True)")
    
    # Event in neighbor hex
    neighbors = list(h3.grid_disk(hex_id, 1))
    neighbor_hex = neighbors[1] if neighbors[1] != hex_id else neighbors[0]
    n_lat, n_lon = h3.cell_to_latlng(neighbor_hex)
    
    print("\nCase 2: Event in neighbor hex")
    relevant = h3_service.is_event_relevant(n_lat, n_lon, route_hexes)
    print(f"Relevant: {relevant} (Expected: True)")
    
    # Event far away
    far_lat, far_lon = 13.0, 77.0
    print("\nCase 3: Event far away")
    relevant = h3_service.is_event_relevant(far_lat, far_lon, route_hexes)
    print(f"Relevant: {relevant} (Expected: False)")

    print("\nH3 Logic Test Complete.")

if __name__ == "__main__":
    test_h3_logic()
