"""
Google Maps Directions API client.

Provides routing functionality using Google Maps Directions API.
API key is loaded from environment variables - never hardcoded.
"""

import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class GoogleMapsClient:
    """
    Client for Google Maps Directions API.
    
    Requires GOOGLE_MAPS_API_KEY environment variable to be set.
    """
    
    BASE_URL = "https://maps.googleapis.com/maps/api/directions/json"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Google Maps client.
        
        Args:
            api_key: Google Maps API key. If None, client is not configured.
        """
        self.api_key = api_key
        self.is_configured = bool(api_key)
        
        if not self.is_configured:
            logger.warning("GoogleMapsClient initialized without API key")
    
    async def get_route(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        mode: str = "driving"
    ) -> Optional[Dict[str, Any]]:
        """
        Get route from Google Maps Directions API.
        
        Args:
            start_lat: Starting latitude
            start_lon: Starting longitude
            end_lat: Ending latitude
            end_lon: Ending longitude
            mode: Travel mode (driving, walking, bicycling, transit)
        
        Returns:
            Route data in Google Maps format, or None on failure
        """
        if not self.is_configured:
            logger.debug("Google Maps client not configured, skipping")
            return None
        
        try:
            # Map mode to Google Maps mode
            mode_map = {
                "car": "driving",
                "driving": "driving",
                "walk": "walking",
                "walking": "walking",
                "bike": "bicycling",
                "cycling": "bicycling",
                "transit": "transit",
            }
            travel_mode = mode_map.get(mode.lower(), "driving")
            
            # Build request parameters
            params = {
                "origin": f"{start_lat},{start_lon}",
                "destination": f"{end_lat},{end_lon}",
                "mode": travel_mode,
                "key": self.api_key,  # API key from environment
            }
            
            # Make API request
            async with httpx.AsyncClient() as client:
                response = await client.get(self.BASE_URL, params=params, timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check status
                    if data.get("status") == "OK":
                        logger.info("Google Maps route retrieved successfully")
                        return data
                    elif data.get("status") == "ZERO_RESULTS":
                        logger.warning("Google Maps returned no routes")
                        return None
                    elif data.get("status") == "REQUEST_DENIED":
                        logger.error("Google Maps API request denied - check API key")
                        return None
                    elif data.get("status") == "OVER_QUERY_LIMIT":
                        logger.warning("Google Maps API quota exceeded")
                        return None
                    else:
                        logger.warning(f"Google Maps API status: {data.get('status')}")
                        return None
                
                else:
                    logger.warning(
                        f"Google Maps API error: {response.status_code} - {response.text[:200]}"
                    )
                    return None
        
        except httpx.TimeoutException:
            logger.error("Google Maps API request timeout")
            return None
        
        except Exception as e:
            logger.error(f"Google Maps API exception: {e}")
            return None
    
    def parse_route_response(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse Google Maps route response into standardized format.
        
        Args:
            response: Raw Google Maps API response
        
        Returns:
            Standardized route data with geometry, distance, duration, steps
        """
        try:
            if not response or "routes" not in response:
                return None
            
            route = response["routes"][0]
            leg = route["legs"][0]
            
            # Extract polyline
            polyline = route.get("overview_polyline", {}).get("points", "")
            
            # Extract distance (meters) and duration (seconds)
            distance = leg.get("distance", {}).get("value", 0)
            duration = leg.get("duration", {}).get("value", 0)
            
            # Extract steps
            steps = leg.get("steps", [])
            
            return {
                "geometry": polyline,  # Encoded polyline
                "distance": distance,
                "duration": duration,
                "steps": steps,
                "provider": "google"
            }
        
        except Exception as e:
            logger.error(f"Error parsing Google Maps response: {e}")
            return None
