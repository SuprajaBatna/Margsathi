"""
Mapbox Directions API client.

Provides routing functionality using Mapbox Directions API v5.
API key is loaded from environment variables - never hardcoded.
"""

import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class MapboxClient:
    """
    Client for Mapbox Directions API.
    
    Requires MAPBOX_API_KEY environment variable to be set.
    """
    
    BASE_URL = "https://api.mapbox.com/directions/v5"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Mapbox client.
        
        Args:
            api_key: Mapbox access token. If None, client is not configured.
        """
        self.api_key = api_key
        self.is_configured = bool(api_key)
        
        if not self.is_configured:
            logger.warning("MapboxClient initialized without API key")
    
    async def get_route(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        mode: str = "driving",
        avoid_point: Optional[Dict[str, float]] = None,
        alternatives: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get route from Mapbox Directions API.
        
        Args:
            start_lat, start_lon: Starting coordinates
            end_lat, end_lon: Destination coordinates
            mode: Routing mode (driving, walking, cycling)
            avoid_point: Optional dict with 'lat', 'lon' to avoid
            
        Returns:
            Route data or None if failed
        """
        if not self.is_configured:
            logger.debug("Mapbox client not configured, skipping")
            return None
        
        try:
            # Map mode to Mapbox profile
            profile_map = {
                "car": "driving",
                "driving": "driving",
                "walk": "walking",
                "walking": "walking",
                "bike": "cycling",
                "cycling": "cycling",
            }
            profile = profile_map.get(mode.lower(), "driving")
            
            # Build request URL
            # Format: /mapbox/{profile}/{coordinates}
            coordinates = f"{start_lon},{start_lat};{end_lon},{end_lat}"
            url = f"{self.BASE_URL}/mapbox/{profile}/{coordinates}"
            
            # Query parameters
            params = {
                "geometries": "polyline6",  # Use polyline6 format (same as OSRM)
                "steps": "true",  # Include turn-by-turn steps
                "overview": "full",  # Full route geometry
                "access_token": self.api_key,  # API key from environment
            }

            # Add alternatives if requested
            if alternatives:
                params["alternatives"] = "true"

            # Add avoid_point if provided (Format: point(lon lat,radius))
            if avoid_point and "lat" in avoid_point and "lon" in avoid_point:
                exclude_param = f"point({avoid_point['lon']} {avoid_point['lat']},500)"
                params["exclude"] = exclude_param
                params["alternatives"] = "true" # Always helpful when avoiding
                logger.info(f"Requesting route with exclusion area: {exclude_param}")
                
            # Make API request
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check if routes were found
                    if data.get("routes") and len(data["routes"]) > 0:
                        logger.info("Mapbox route retrieved successfully")
                        return data
                    else:
                        logger.warning("Mapbox returned no routes")
                        return None
                
                elif response.status_code == 401:
                    logger.error("Mapbox API authentication failed - invalid API key")
                    return None
                
                elif response.status_code == 429:
                    logger.warning("Mapbox API rate limit exceeded")
                    return None
                
                else:
                    logger.warning(
                        f"Mapbox API error: {response.status_code} - {response.text[:200]}"
                    )
                    return None
        
        except httpx.TimeoutException:
            logger.error("Mapbox API request timeout")
            return None
        
        except Exception as e:
            logger.error(f"Mapbox API exception: {e}")
            return None
    
    def parse_route_response(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse Mapbox route response into standardized format.
        
        Args:
            response: Raw Mapbox API response
        
        Returns:
            Standardized route data with geometry, distance, duration, steps
        """
        try:
            if not response or "routes" not in response:
                return None
            
            route = response["routes"][0]
            
            # Extract geometry (GeoJSON format)
            geometry = route.get("geometry", {})
            
            # Extract distance (meters) and duration (seconds)
            distance = route.get("distance", 0)
            duration = route.get("duration", 0)
            
            # Extract steps from legs
            steps = []
            for leg in route.get("legs", []):
                steps.extend(leg.get("steps", []))
            
            return {
                "geometry": geometry,
                "distance": distance,
                "duration": duration,
                "steps": steps,
                "provider": "mapbox"
            }
        
        except Exception as e:
            logger.error(f"Error parsing Mapbox response: {e}")
            return None
