"""
Centralized configuration for routing service providers.

This module loads API keys from environment variables and provides
configuration for multiple routing providers with fallback support.
"""

import os
import logging
from typing import Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class RoutingProvider(str, Enum):
    """Supported routing service providers."""
    MAPBOX = "mapbox"
    GOOGLE_MAPS = "google"
    MAPMYINDIA = "mapmyindia"
    OSRM = "osrm"


class RoutingConfig:
    """Configuration manager for routing services."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        # Load API keys from environment (never hardcode!)
        self.mapbox_api_key = os.getenv("MAPBOX_API_KEY")
        self.google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        self.mapmyindia_api_key = os.getenv("MAPMYINDIA_API_KEY")
        self.mapmyindia_client_id = os.getenv("MAPMYINDIA_CLIENT_ID")
        self.mapmyindia_client_secret = os.getenv("MAPMYINDIA_CLIENT_SECRET")
        
        # OSRM configuration (no key required)
        self.osrm_base_url = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")
        
        # Preferred provider (can be overridden via env var)
        preferred = os.getenv("ROUTING_PROVIDER", "osrm").lower()
        try:
            self.preferred_provider = RoutingProvider(preferred)
        except ValueError:
            logger.warning(f"Invalid ROUTING_PROVIDER '{preferred}', defaulting to OSRM")
            self.preferred_provider = RoutingProvider.OSRM
        
        # Log configuration status (without exposing keys!)
        self._log_config_status()
    
    def _log_config_status(self):
        """Log which providers are configured (without exposing keys)."""
        status = {
            "Mapbox": "✓ Configured" if self.mapbox_api_key else "✗ No API key",
            "Google Maps": "✓ Configured" if self.google_maps_api_key else "✗ No API key",
            "MapMyIndia": "✓ Configured" if self.mapmyindia_api_key else "✗ No API key",
            "OSRM": "✓ Available (no key required)",
        }
        
        logger.info("Routing Provider Configuration:")
        for provider, state in status.items():
            logger.info(f"  {provider}: {state}")
        logger.info(f"  Preferred Provider: {self.preferred_provider.value}")
    
    def is_provider_configured(self, provider: RoutingProvider) -> bool:
        """Check if a specific provider is properly configured."""
        if provider == RoutingProvider.MAPBOX:
            return bool(self.mapbox_api_key)
        elif provider == RoutingProvider.GOOGLE_MAPS:
            return bool(self.google_maps_api_key)
        elif provider == RoutingProvider.MAPMYINDIA:
            return bool(self.mapmyindia_api_key) or (
                bool(self.mapmyindia_client_id) and bool(self.mapmyindia_client_secret)
            )
        elif provider == RoutingProvider.OSRM:
            return True  # OSRM doesn't require API key
        return False
    
    def get_available_providers(self) -> List[RoutingProvider]:
        """Get list of all configured providers."""
        return [
            provider for provider in RoutingProvider
            if self.is_provider_configured(provider)
        ]
    
    def get_fallback_chain(self) -> List[RoutingProvider]:
        """
        Get the provider fallback chain.
        
        Returns providers in order of preference:
        1. Preferred provider (if configured)
        2. Other configured providers
        3. OSRM (always available as last resort)
        """
        chain = []
        
        # Add preferred provider first if configured
        if self.is_provider_configured(self.preferred_provider):
            chain.append(self.preferred_provider)
        
        # Add other configured providers
        for provider in RoutingProvider:
            if provider != self.preferred_provider and self.is_provider_configured(provider):
                chain.append(provider)
        
        # Ensure OSRM is always last as fallback
        if RoutingProvider.OSRM not in chain:
            chain.append(RoutingProvider.OSRM)
        
        return chain


# Global configuration instance
routing_config = RoutingConfig()
