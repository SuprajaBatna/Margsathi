"""
Router Manager - Unified interface for multiple routing providers.

Manages provider selection, fallback logic, and provides a single
interface for routing requests across multiple providers.
"""

import logging
from typing import Optional, Dict, Any, List
from backend.config import routing_config, RoutingProvider
from backend.services.mapbox import MapboxClient
from backend.services.google_maps import GoogleMapsClient
from backend.services.mapmyindia import MapMyIndiaClient
from backend.services.osrm import OSRMClient

logger = logging.getLogger(__name__)


class RouterManager:
    """
    Manages routing across multiple providers with automatic fallback.
    
    Providers are tried in order of preference. If one fails, the next
    is attempted automatically.
    """
    
    def __init__(self):
        """Initialize all available routing providers."""
        self.config = routing_config
        
        # Initialize provider clients
        self.providers = {
            RoutingProvider.MAPBOX: MapboxClient(self.config.mapbox_api_key),
            RoutingProvider.GOOGLE_MAPS: GoogleMapsClient(self.config.google_maps_api_key),
            RoutingProvider.MAPMYINDIA: MapMyIndiaClient(),
            RoutingProvider.OSRM: OSRMClient(),
        }
        
        # Get fallback chain
        self.fallback_chain = self.config.get_fallback_chain()
        
        logger.info(f"RouterManager initialized with fallback chain: {[p.value for p in self.fallback_chain]}")
    
    async def get_route(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        mode: str = "driving",
        preferred_provider: Optional[Any] = None, # Can be RoutingProvider or string
        avoid_point: Optional[Dict[str, float]] = None,
        alternatives: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Get route using available providers with automatic fallback.
        """
        # Convert string provider to Enum if needed
        if isinstance(preferred_provider, str):
            try:
                preferred_provider = RoutingProvider(preferred_provider.lower())
            except ValueError:
                preferred_provider = None

        # Determine provider order
        if preferred_provider and self.config.is_provider_configured(preferred_provider):
            # Try preferred provider first, then fallback chain
            provider_order = [preferred_provider] + [
                p for p in self.fallback_chain if p != preferred_provider
            ]
        else:
            provider_order = self.fallback_chain
        
        # Try each provider in order
        for provider in provider_order:
            try:
                # SKIP providers that don't support avoidance if avoid_point is set
                # Currently only Mapbox supports it
                if avoid_point and provider != RoutingProvider.MAPBOX:
                    logger.info(f"Skipping {provider.value} because it doesn't support avoid_point")
                    continue

                logger.info(f"Attempting route with provider: {provider.value}")
                
                client = self.providers[provider]
                
                # Pass avoid_point only if provider supports it
                if provider == RoutingProvider.MAPBOX:
                     result = await client.get_route(start_lat, start_lon, end_lat, end_lon, mode, avoid_point=avoid_point, alternatives=alternatives)
                else:
                     result = await client.get_route(start_lat, start_lon, end_lat, end_lon, mode)
                
                if result:
                    logger.info(f"Route successfully retrieved from {provider.value}")
                    
                    # Add provider metadata
                    if isinstance(result, dict):
                        # Ensure we return the provider as a string for the frontend/client
                        result["_provider_used"] = provider.value
                    
                    return result
                else:
                    logger.warning(f"Provider {provider.value} returned no route, trying next")
            
            except Exception as e:
                logger.error(f"Provider {provider.value} failed with error: {e}, trying next")
                continue
        
        # All providers failed
        logger.error("All routing providers failed")
        return None
    
    def get_provider_status(self) -> Dict[str, Any]:
        """
        Get status of all providers (for debugging/monitoring).
        
        Returns:
            Dictionary with provider configuration status
        """
        return {
            "configured_providers": [p.value for p in self.config.get_available_providers()],
            "preferred_provider": self.config.preferred_provider.value,
            "fallback_chain": [p.value for p in self.fallback_chain],
            "provider_details": {
                provider.value: {
                    "configured": self.config.is_provider_configured(provider),
                    "requires_key": provider != RoutingProvider.OSRM
                }
                for provider in RoutingProvider
            }
        }


# Global router manager instance
router_manager = RouterManager()
