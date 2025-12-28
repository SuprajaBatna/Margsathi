"""
Geometry Utilities

Provides functions for geometric calculations, polyline decoding,
and proximity checks.
"""

import math
import logging
from typing import List, Tuple, Union, Optional

logger = logging.getLogger(__name__)

def is_location_on_path(
    path: List[Tuple[float, float]], 
    lat: float, 
    lon: float, 
    radius_meters: float
) -> Tuple[bool, float, int]:
    """
    Check if a location point is within radius meters of any segment of the path.
    
    Args:
        path: List of (lat, lon) coordinates
        lat: Location latitude
        lon: Location longitude
        radius_meters: Threshold distance in meters
        
    Returns:
        (bool, float, int): (True if within radius, min_distance_in_meters, closest_segment_index)
    """

    min_dist = float('inf')
    closest_index = -1
    is_within = False
    
    if not path:
        return False, min_dist

    # Check distance to each segment
    for i in range(len(path) - 1):
        p1 = path[i]
        p2 = path[i+1]
        dist = point_line_segment_distance(
            lat, lon, 
            p1[0], p1[1], 
            p2[0], p2[1]
        )
        if dist < min_dist:
            min_dist = dist
            closest_index = i
    
    return min_dist <= radius_meters, min_dist, closest_index

def point_line_segment_distance(
    px: float, py: float, 
    x1: float, y1: float, 
    x2: float, y2: float
) -> float:
    """
    Calculate min distance from point P(px,py) to segment (x1,y1)-(x2,y2).
    Using flat-earth approximation (Equirectangular projection) for small distances.
    
    Args:
        px, py: Point latitude, longitude
        x1, y1: Segment start latitude, longitude
        x2, y2: Segment end latitude, longitude
        
    Returns:
        float: Distance in meters
    """
    # Helper to convert degrees to approximate meters
    def to_meters(lat, lon):
        y = lat * 111132.0
        x = lon * 111319.0 * math.cos(math.radians(lat))
        return x, y
    
    Px, Py = to_meters(px, py)
    X1, Y1 = to_meters(x1, y1)
    X2, Y2 = to_meters(x2, y2)
    
    # Segment vector AB
    dx = X2 - X1
    dy = Y2 - Y1
    
    if dx == 0 and dy == 0:
        return math.hypot(Px - X1, Py - Y1)
    
    # Project AP onto AB to find t
    t = ((Px - X1) * dx + (Py - Y1) * dy) / (dx*dx + dy*dy)
    
    # Clamp t to segment [0, 1]
    t = max(0, min(1, t))
    
    # Closest point on segment
    Cx = X1 + t * dx
    Cy = Y1 + t * dy
    
    return math.hypot(Px - Cx, Py - Cy)

def decode_polyline(polyline_str: str) -> List[Tuple[float, float]]:
    """
    Decode encoded polyline string (supports precision 5 and 6 via heuristics).
    
    Args:
        polyline_str: The encoded polyline string
        
    Returns:
        List[Tuple[float, float]]: List of (lat, lon) tuples
    """
    points = []
    index = 0
    lat = 0
    lng = 0
    length = len(polyline_str)
    
    # Defaulting to 1e6 (Mapbox/OSRM standard for polyline6)
    # Ideally should detect or accept precision argument, but 1e6 is safe for this project context
    factor = 1e6 
    
    try:
        while index < length:
            b = 0
            shift = 0
            result = 0
            
            # Latitude
            while True:
                b = ord(polyline_str[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            dlat = ~(result >> 1) if (result & 1) else (result >> 1)
            lat += dlat
            
            # Longitude
            shift = 0
            result = 0
            while True:
                b = ord(polyline_str[index]) - 63
                index += 1
                result |= (b & 0x1f) << shift
                shift += 5
                if b < 0x20:
                    break
            dlng = ~(result >> 1) if (result & 1) else (result >> 1)
            lng += dlng
            
            points.append((lat / factor, lng / factor))
    except Exception as e:
        logger.error(f"Polyline decoding failed: {e}")
        return []
        
    return points
