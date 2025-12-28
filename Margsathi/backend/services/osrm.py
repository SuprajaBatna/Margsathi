import httpx
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class OSRMClient:
    """
    Client for OSRM (Open Source Routing Machine) API.
    Uses the public demo server by default.
    """

    BASE_URL = "https://router.project-osrm.org/route/v1"

    async def get_route(
        self, 
        start_lat: float, 
        start_lon: float, 
        end_lat: float, 
        end_lon: float, 
        mode: str = "driving"
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch route from OSRM.
        Returns raw JSON response or None on failure.
        """
        # Determine profile
        profile = "driving"
        if mode == "bike": profile = "bicycle"
        if mode == "walk": profile = "foot"
        
        # OSRM coordinates format: {longitude},{latitude};{longitude},{latitude}
        coords = f"{start_lon},{start_lat};{end_lon},{end_lat}"
        url = f"{self.BASE_URL}/{profile}/{coords}"
        
        params = {
            "overview": "full",
            "geometries": "polyline6",
            "steps": "true"
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params, timeout=10.0)
                if resp.status_code == 200:
                    return resp.json()
                else:
                    logger.warning(f"OSRM API Error: {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"OSRM Service Exception: {e}")

        return None
