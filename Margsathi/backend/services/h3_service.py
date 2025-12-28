import h3
import logging
from typing import List, Tuple, Set, Dict, Any
from backend.utils.geometry import decode_polyline

logger = logging.getLogger(__name__)

class H3Service:
    """
    Uber H3 spatial indexing service for city-level routing analysis.
    """
    
    def __init__(self, resolution: int = 9):
        self.resolution = resolution

    def latlng_to_hex(self, lat: float, lon: float) -> str:
        """Convert lat/lng to H3 hex ID."""
        return h3.latlng_to_cell(lat, lon, self.resolution)

    def get_route_hexes(self, polyline_str: str, precision: int = 6) -> Set[str]:
        """
        Convert encoded polyline to a set of H3 hex IDs.
        Decodes the polyline and maps each point to a hex.
        """
        try:
            points = decode_polyline(polyline_str)
            if not points:
                return set()
                
            hexes = set()
            for lat, lon in points:
                hex_id = self.latlng_to_hex(lat, lon)
                hexes.add(hex_id)
            return hexes
        except Exception as e:
            logger.error(f"Error converting route to H3: {e}")
            return set()

    def is_event_relevant(self, event_lat: float, event_lon: float, route_hexes: Set[str], k_neighbors: int = 1) -> bool:
        """
        Check if an event affects the current route.
        An event is relevant if its H3 cell OR its neighbors (k=1) overlap with route H3 cells.
        """
        event_hex = self.latlng_to_hex(event_lat, event_lon)
        
        # 1. Direct overlap
        if event_hex in route_hexes:
            logger.info(f"H3 Match: Event {event_hex} is directly on the route.")
            return True
            
        # 2. Neighbor overlap (k=1 means immediate 6 neighbors + center)
        neighbors = h3.grid_disk(event_hex, k_neighbors)
        for neighbor in neighbors:
            if neighbor in route_hexes:
                logger.info(f"H3 Near Match: Event neighbor {neighbor} intersects route.")
                return True
                
        return False

    def get_hex_center(self, hex_id: str) -> Tuple[float, float]:
        """Get the center lat/lng of a hex."""
        return h3.cell_to_latlng(hex_id)

    def get_avoidance_points(self, event_lat: float, event_lon: float, radius_hexes: int = 1) -> List[Dict[str, float]]:
        """
        Returns centers of H3 hexes to avoid.
        Used for the routing engine to avoid specific sectors.
        """
        event_hex = self.latlng_to_hex(event_lat, event_lon)
        neighbors = h3.grid_disk(event_hex, radius_hexes)
        
        avoidance_points = []
        for h_id in neighbors:
            lat, lon = self.get_hex_center(h_id)
            avoidance_points.append({"lat": lat, "lon": lon})
            
        return avoidance_points

    def validate_route_avoidance(self, polyline_str: str, restricted_hexes: Set[str]) -> bool:
        """
        Validates that a route does NOT pass through restricted hexes.
        Returns True if the route is safe, False if it intersects.
        """
        route_hexes = self.get_route_hexes(polyline_str)
        intersection = route_hexes.intersection(restricted_hexes)
        if intersection:
            logger.warning(f"Route validation FAILED. Intersects {len(intersection)} restricted hexes.")
            return False
        return True

    def get_bearing(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """Calculate bearing between two points in degrees."""
        import math
        lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
        lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
        
        d_lon = lon2 - lon1
        y = math.sin(d_lon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(d_lon)
        
        bearing = math.atan2(y, x)
        return (math.degrees(bearing) + 360) % 360

    def get_perpendicular_point(self, lat: float, lon: float, bearing: float, distance_km: float, side: str = 'left') -> Tuple[float, float]:
        """Calculate a point at a distance perpendicular to a bearing."""
        import math
        # Perpendicular bearing
        if side == 'left':
            p_bearing = (bearing - 90 + 360) % 360
        else:
            p_bearing = (bearing + 90) % 360
            
        # Earth radius in km
        R = 6371.0
        p_lat = math.radians(lat)
        p_lon = math.radians(lon)
        brng = math.radians(p_bearing)
        
        new_lat = math.asin(math.sin(p_lat) * math.cos(distance_km/R) +
                          math.cos(p_lat) * math.sin(distance_km/R) * math.cos(brng))
        new_lon = p_lon + math.atan2(math.sin(brng) * math.sin(distance_km/R) * math.cos(p_lat),
                                    math.cos(distance_km/R) - math.sin(p_lat) * math.sin(new_lat))
        
        return (math.degrees(new_lat), math.degrees(new_lon))

# Default instance with resolution 9 (~174m edge length)
h3_service = H3Service(resolution=9)
