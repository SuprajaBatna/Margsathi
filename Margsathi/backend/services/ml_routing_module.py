import logging
from typing import Dict, Any, Optional, Union, List
from backend.services.ml_inference import traffic_detector
from backend.services.router_manager import router_manager
from backend.config import routing_config, RoutingProvider

# Configure logger
logger = logging.getLogger(__name__)

class MLRoutingModule:
    """
    Machine Learning-based Routing Decision Module.
    Reacts to events by predicting impact and generating autonomous detours.
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
        Predict impact of an event and generate an optimized detour if necessary.
        """
        # Defensive extraction for Pydantic objects or Dicts
        ev_lat = event_data.get("lat") if isinstance(event_data, dict) else getattr(event_data, "lat", None)
        ev_lon = event_data.get("lon") if isinstance(event_data, dict) else getattr(event_data, "lon", None)
        ev_type = event_data.get("type", "Traffic Event") if isinstance(event_data, dict) else getattr(event_data, "type", "Traffic Event")
        
        src_lat = source.get("lat") if isinstance(source, dict) else getattr(source, "lat", None)
        src_lon = source.get("lon") if isinstance(source, dict) else getattr(source, "lon", None)
        
        dst_lat = destination.get("lat") if isinstance(destination, dict) else getattr(destination, "lat", None)
        dst_lon = destination.get("lon") if isinstance(destination, dict) else getattr(destination, "lon", None)

        logger.info(f"ML Module evaluating impact for event at ({ev_lat}, {ev_lon})")

        # 1. Prediction (Using ML Inference)
        ml_input = {
            "type": "event_proxy",
            "lat": ev_lat,
            "lon": ev_lon,
            "force_event": ev_type,
            "confidence": 0.85 
        }
        
        prediction = traffic_detector.predict(ml_input)
        logger.info(f"ML Prediction Confidence: {prediction.confidence:.2f}")

        # 2. Impact Decision
        if prediction.confidence > 0.6:
            logger.info(f"ML Module predicts SIGNIFICANT impact at ({ev_lat}, {ev_lon}). Generating autonomous detour.")

            # 3. Generate NEW optimized route using a Waypoint Nudge
            # We calculate a point slightly offset to force a detour
            # Shift of ~0.01 is about 1.1km. We use a diagonal nudge.
            nudge_lat = ev_lat + 0.01
            nudge_lon = ev_lon + 0.01
            
            logger.info(f"Forcing detour via nudge waypoint: ({nudge_lat}, {nudge_lon})")
            
            new_route = await self._get_nudged_route(
                src_lat, src_lon, 
                nudge_lat, nudge_lon, 
                dst_lat, dst_lon, 
                mode
            )

            if new_route and new_route.get("routes"):
                logger.info("ML Module successfully generated a nudged detour.")
                # Basic validation: is it different?
                r = new_route["routes"][0]
                if r.get("geometry") != current_geometry:
                    logger.info(f"Nudged route is GEOMETRICALLY DISTINCT. Distance: {r.get('distance')}m")
                else:
                    logger.warning("Nudged route is GEOMETRICALLY IDENTICAL to baseline despite nudge point.")
                
                new_route["_is_ml_detour"] = True
                return new_route
            else:
                logger.error("ML Module failed to generate a nudged route (API returned no routes or error).")
            
        return None

    async def _get_nudged_route(self, s_lat, s_lon, n_lat, n_lon, d_lat, d_lon, mode):
        """Internal helper to get a route through a nudge point."""
        from backend.config import routing_config
        
        # Profile mapping
        profile_map = {"car": "driving", "driving": "driving", "walk": "walking", "bike": "cycling"}
        profile = profile_map.get(mode, "driving")
        
        coords = f"{s_lon},{s_lat};{n_lon},{n_lat};{d_lon},{d_lat}"
        url = f"https://api.mapbox.com/directions/v5/mapbox/{profile}/{coords}"
        params = {
            "access_token": routing_config.mapbox_api_key,
            "geometries": "polyline6",
            "overview": "full",
            "steps": "true",
            "alternatives": "false" # Keep it simple for nudging
        }
        
        logger.info(f"Requesting Nudged Route: {url}")
        
        import httpx
        async with httpx.AsyncClient() as h_client:
            try:
                resp = await h_client.get(url, params=params, timeout=10.0)
                logger.info(f"Mapbox Nudge Response Status: {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("routes"):
                        return data
                    else:
                        logger.warning(f"Mapbox returned 200 but no routes: {data}")
                else:
                    logger.error(f"Mapbox Nudge API Error: {resp.text}")
            except Exception as e:
                logger.error(f"Nudged route request exception: {e}")
        return None

# Singleton instance
ml_routing_module = MLRoutingModule()
