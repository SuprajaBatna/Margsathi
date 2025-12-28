"""
Mapbox Geocoding API service.

Provides geocoding (place name to coordinates) using Mapbox Geocoding API.
Enables routing between any locations worldwide.
"""

import httpx
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class MapboxGeocoder:
    """
    Client for Mapbox Geocoding API.
    
    Converts place names to coordinates for routing.
    """
    
    BASE_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Mapbox geocoder.
        
        Args:
            api_key: Mapbox access token. If None, geocoding is disabled.
        """
        self.api_key = api_key
        self.is_configured = bool(api_key)
        
        if not self.is_configured:
            logger.warning("MapboxGeocoder initialized without API key")
    
    async def geocode(self, place_name: str, country: str = "in") -> Optional[Dict[str, Any]]:
        """
        Geocode a place name to coordinates.
        
        Args:
            place_name: Name of the place (e.g., "Visakhapatnam", "New York")
            country: ISO country code for better results (default: "in" for India)
        
        Returns:
            Dictionary with lat, lon, display name, or None if not found
        """
        if not self.is_configured:
            logger.debug("Mapbox geocoder not configured, skipping")
            return None
        
        try:
            # Clean up place name
            query = place_name.strip()
            
            # Build request URL
            # Format: /mapbox.places/{query}.json
            url = f"{self.BASE_URL}/{query}.json"
            
            # Query parameters
            params = {
                "access_token": self.api_key,
                "country": country,  # Limit to specific country for better results
                "limit": 10,  # Fetch more to allow filtering for 'place' types
                "types": "place,locality,address",  # Focus on cities/addresses
            }
            
            # Make API request
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=5.0)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Check if any results found
                    if data.get("features") and len(data["features"]) > 0:
                        features = data["features"]
                        selected_feature = features[0] # Default to first
                        
                        # PREFER PLACE/LOCALITY:
                        # Scan top results to see if there is a 'place' or 'locality' match
                        # This fixes issues where "Bangalore" matches "Bangalore Highway" (address)
                        for f in features:
                            # Mapbox IDs are like "place.1234" or "address.5678"
                            fid = f.get("id", "")
                            if fid.startswith("place") or fid.startswith("locality") or fid.startswith("district"):
                                selected_feature = f
                                break
                        
                        # Extract coordinates [lon, lat] format
                        coordinates = selected_feature.get("geometry", {}).get("coordinates", [])
                        if len(coordinates) >= 2:
                            lon, lat = coordinates[0], coordinates[1]
                            
                            # Extract place name
                            display_name = selected_feature.get("place_name", place_name)
                            # Use text for shorter name
                            short_name = selected_feature.get("text", display_name)
                            
                            logger.info(f"Geocoded '{place_name}' → {short_name} ({lat}, {lon}) [Type: {selected_feature.get('id', 'unknown')}]")
                            
                            return {
                                "lat": lat,
                                "lon": lon,
                                "display": short_name,
                                "full_name": display_name
                            }
                        else:
                            logger.warning(f"Mapbox returned no coordinates for '{place_name}'")
                            return None
                    else:
                        logger.warning(f"Mapbox found no results for '{place_name}'")
                        return None
                
                elif response.status_code == 401:
                    logger.error("Mapbox Geocoding API authentication failed")
                    return None
                
                elif response.status_code == 429:
                    logger.warning("Mapbox Geocoding API rate limit exceeded")
                    return None
                
                else:
                    logger.warning(
                        f"Mapbox Geocoding API error: {response.status_code} - {response.text[:200]}"
                    )
                    return None
        
        except httpx.TimeoutException:
            logger.error("Mapbox Geocoding API request timeout")
            return None
        
        except Exception as e:
            logger.error(f"Mapbox Geocoding API exception: {e}")
            return None
    
    async def geocode_batch(self, place_names: list[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Geocode multiple places (useful for source + destination).
        
        Args:
            place_names: List of place names to geocode
        
        Returns:
            Dictionary mapping place names to geocoding results
        """
        results = {}
        for place_name in place_names:
            results[place_name] = await self.geocode(place_name)
        return results
