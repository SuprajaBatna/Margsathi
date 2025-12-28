import h3
import logging
import asyncio
import httpx
from typing import Dict, Any, Optional, Union, List, Set
from backend.services.h3_service import h3_service
from backend.services.ml_inference import traffic_detector
from backend.config import routing_config, RoutingProvider

logger = logging.getLogger(__name__)

class H3RoutingModule:
    """
    Intelligent Rerouting Module using Uber H3 Spatial Indexing.
    Triggers rerouting ONLY when events spatially intersect the route.
    """
    
    async def predict_and_reroute(
        self,
        event_data: Union[Dict[str, Any], Any],
        source: Union[Dict[str, float], Any],
        destination: Union[Dict[str, float], Any],
        current_geometry: str,
        mode: str = "driving",
        initial_provider: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate impact and generate a detour with DYNAMIC spatial logic.
        """
        # 1. Extract coordinates
        ev_lat = event_data.get("lat") if isinstance(event_data, dict) else getattr(event_data, "lat", None)
        ev_lon = event_data.get("lon") if isinstance(event_data, dict) else getattr(event_data, "lon", None)
        affected_radius = event_data.get("affected_radius", 500) # Default to 500m
        
        src_lat = source.get("lat") if isinstance(source, dict) else getattr(source, "lat", None)
        src_lon = source.get("lon") if isinstance(source, dict) else getattr(source, "lon", None)
        
        dst_lat = destination.get("lat") if isinstance(destination, dict) else getattr(destination, "lat", None)
        dst_lon = destination.get("lon") if isinstance(destination, dict) else getattr(destination, "lon", None)

        if not ev_lat or not ev_lon or not current_geometry:
            return None

        # 2. H3 Relevance & Dynamic Scaling
        route_hexes = h3_service.get_route_hexes(current_geometry)
        
        # Scaling K-radius: Res 9 hex is ~350m across. k=1 is ~700m, k=2 is ~1km+.
        k_radius = max(1, int(affected_radius / 350))
        is_relevant = h3_service.is_event_relevant(ev_lat, ev_lon, route_hexes, k_neighbors=k_radius)
        
        if not is_relevant:
            logger.info("H3 Module: Dynamic audit shows event is out of range. No reroute.")
            return None

        # Define the restricted zone based on dynamic radius
        event_hex = h3_service.latlng_to_hex(ev_lat, ev_lon)
        restricted_hexes = set(h3.grid_disk(event_hex, k_radius))

        # 3. Dynamic Nudge Calculation
        # Get bearing of current route near the incident
        local_bearing = self._get_local_bearing(current_geometry, ev_lat, ev_lon)
        
        # Iterative Rerouting Loop with varying directions/distances
        # We try: [Left 2km, Right 2km, Left 3km, Right 3km...]
        nudge_options = []
        for dist in [2.0, 3.5]: # Distances in km
            n_left = h3_service.get_perpendicular_point(ev_lat, ev_lon, local_bearing, dist, 'left')
            n_right = h3_service.get_perpendicular_point(ev_lat, ev_lon, local_bearing, dist, 'right')
            nudge_options.append(n_left)
            nudge_options.append(n_right)

        avoid_cells = h3_service.get_avoidance_points(ev_lat, ev_lon, radius_hexes=k_radius)
        
        final_route = None
        for i, nudge_pt in enumerate(nudge_options):
            logger.info(f"Rerouting Attempt {i+1} with dynamic point: {nudge_pt}")
            
            candidate_resp = await self._get_nudged_route(
                src_lat, src_lon, 
                nudge_pt[0], nudge_pt[1], 
                dst_lat, dst_lon, 
                mode,
                avoid_cells
            )
            
            if candidate_resp and candidate_resp.get("routes"):
                candidate_geom = candidate_resp["routes"][0].get("geometry")
                
                # STRICT VALIDATION
                is_safe = h3_service.validate_route_avoidance(candidate_geom, restricted_hexes)
                
                if is_safe and candidate_geom != current_geometry:
                    logger.info(f"SUCCESS: Dynamic alternate route found on attempt {i+1}.")
                    final_route = candidate_resp
                    break
        
        if final_route:
            logger.info("Simulation: 5 second processing delay...")
            await asyncio.sleep(5)
            final_route["_is_ml_detour"] = True
            return final_route
        
        logger.error("H3 Module: Failed to find valid avoidance path.")
        return None

    def _get_local_bearing(self, current_geometry: str, ev_lat: float, ev_lon: float) -> float:
        """Finds the bearing of the route segment closest to the incident."""
        from backend.utils.geometry import decode_polyline
        points = decode_polyline(current_geometry)
        if len(points) < 2: return 0.0
        
        # Find closest point
        min_dist = float('inf')
        closest_idx = 0
        for i, (p_lat, p_lon) in enumerate(points):
            dist = (p_lat - ev_lat)**2 + (p_lon - ev_lon)**2
            if dist < min_dist:
                min_dist = dist
                closest_idx = i
        
        # Get next point for bearing, or previous if at the end
        if closest_idx < len(points) - 1:
            return h3_service.get_bearing(points[closest_idx], points[closest_idx+1])
        else:
            return h3_service.get_bearing(points[closest_idx-1], points[closest_idx])

    async def _get_nudged_route(self, s_lat, s_lon, n_lat, n_lon, d_lat, d_lon, mode, avoid_cells):
        """Mapbox Directions API multi-point request with cluster-based exclusion zone."""
        profile_map = {"car": "driving", "driving": "driving", "walk": "walking", "bike": "cycling"}
        profile = profile_map.get(mode, "driving")
        
        coords = f"{s_lon},{s_lat};{n_lon},{n_lat};{d_lon},{d_lat}"
        url = f"https://api.mapbox.com/directions/v5/mapbox/{profile}/{coords}"
        
        # Format exclusion cluster
        exclude_parts = [f"point({c['lon']} {c['lat']})" for c in avoid_cells[:50]] # Limit to 50 per Mapbox spec
        exclude_param = ",".join(exclude_parts)
        
        params = {
            "access_token": routing_config.mapbox_api_key,
            "geometries": "polyline6",
            "overview": "full",
            "steps": "true",
            "alternatives": "false",
            "exclude": exclude_param 
        }
        
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(url, params=params, timeout=10.0)
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                logger.error(f"H3 detour request failed: {e}")
        return None

# Singleton instance
h3_routing_module = H3RoutingModule()
