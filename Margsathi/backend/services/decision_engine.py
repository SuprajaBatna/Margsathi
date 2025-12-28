"""
Decision Engine Module

Evaluates whether a route should be recalculated based on external events.
"""

import math
from typing import List, Dict, Any, Optional, Tuple, Union
from enum import Enum
import logging

# Configure logger
logger = logging.getLogger(__name__)

from backend.utils.geometry import is_location_on_path, decode_polyline

class Decision(str, Enum):
    REROUTE = "REROUTE"
    CONTINUE = "CONTINUE"

class DecisionEngine:
    """
    Evaluates impact of events on active routes to make routing decisions.
    
    Independent and reusable module.
    """
    
    def __init__(self, default_impact_radius_meters: float = 500.0):
        """
        Initialize the decision engine.
        
        Args:
            default_impact_radius_meters: Default radius to consider an event "on route"
        """
        self.default_radius = default_impact_radius_meters

    def evaluate_impact(
        self,
        route_geometry: Union[str, List[List[float]]],
        event_data: Dict[str, Any],
        current_metrics: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Evaluate if a route needs to be changed due to an event.
        
        Args:
            route_geometry: Encoded polyline string or list of [lat, lon] coordinates
            event_data: Dictionary containing:
                - type: str (e.g., 'Accident', 'Rally')
                - severity: str ('HIGH', 'MEDIUM', 'LOW')
                - lat: float
                - lon: float
                - radius: Optional[float] (affected radius in meters)
            current_metrics: Optional dict with 'distance_meters', 'duration_seconds'
            
        Returns:
            Dict containing:
                - decision: Decision.REROUTE | Decision.CONTINUE
                - reason: str
                - details: dict (impact analysis)
        """
        # 1. Parse Geometry
        path = self._parse_geometry(route_geometry)
        if not path:
            return {
                "decision": Decision.CONTINUE,
                "reason": "Invalid or empty route geometry",
                "details": {}
            }

        # 2. Extract Event Info
        event_lat = float(event_data.get("lat", 0))
        event_lon = float(event_data.get("lon", 0))
        severity = event_data.get("severity", "LOW").upper()
        impact_radius = float(event_data.get("radius", self.default_radius))
        
        # 3. Check Proximity
        is_on_route, min_distance, closest_index = is_location_on_path(path, event_lat, event_lon, impact_radius)
        
        # 4. Make Decision
        # Logic: REROUTE if Severity is HIGH/CRITICAL and Event is ON ROUTE
        decision = Decision.CONTINUE
        reason = "Event does not significantly impact route"
        
        if is_on_route:
            # Check percentage along route (prevent start/end events)
            segment_percentage = (closest_index / len(path)) * 100 if len(path) > 0 else 0
            
            if segment_percentage < 10 or segment_percentage > 90:
                 decision = Decision.CONTINUE
                 reason = f"Event is on route but too close to start/end ({int(segment_percentage)}%). Ignoring."
            elif severity in ["HIGH", "CRITICAL", "SEVERE"]:
                decision = Decision.REROUTE
                reason = f"Critical event ({event_data.get('type', 'Unknown')}) blocking route at {int(segment_percentage)}% mark."
            elif severity == "MEDIUM":
                decision = Decision.CONTINUE
                reason = "Event is on route but severity is not critical"
            else:
                decision = Decision.CONTINUE
                reason = "Low severity event on route, safe to proceed"
        else:
            reason = f"Event is clear of route path (closest point: {int(min_distance)}m away)"

        return {
            "decision": decision,
            "reason": reason,
            "details": {
                "min_distance_meters": round(min_distance, 1),
                "is_on_route": is_on_route,
                "closest_index": closest_index,
                "segment_percentage": round((closest_index / len(path) * 100) if path else 0, 1),
                "impact_radius": impact_radius,
                "event_severity": severity
            }
        }

    async def generate_baseline_route(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        mode: str = "driving",
        preferred_provider: Optional[Any] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate the best optimized route for a given source and destination.
        This represents the 'baseline' route that should remain unchanged unless events occur.
        """
        from backend.services.router_manager import router_manager
        
        logger.info(f"Decision Engine generating baseline route from ({start_lat}, {start_lon}) to ({end_lat}, {end_lon})")
        
        # Use RouterManager to get the best route from available providers
        # Mapbox is usually the default optimized choice in our config
        route = await router_manager.get_route(
            start_lat, start_lon,
            end_lat, end_lon,
            mode=mode,
            preferred_provider=preferred_provider
        )
        
        if route:
            logger.info(f"Baseline route generated successfully using {route.get('_provider_used', 'unknown')}")
            # Ensure the route is marked as baseline if needed (metadata)
            route["_is_baseline"] = True
            
        return route

    def _parse_geometry(self, geometry: Union[str, List[List[float]]]) -> List[Tuple[float, float]]:
        """Convert input geometry to list of (lat, lon) tuples."""
        if isinstance(geometry, list):
            # Assume list of lists/tuples
            return [(float(p[0]), float(p[1])) for p in geometry if len(p) >= 2]
        
        if isinstance(geometry, str):
            return decode_polyline(geometry)
            
        return []

# Singleton instance export
decision_engine = DecisionEngine()
