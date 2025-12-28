from math import radians, cos, sin, asin, sqrt
from typing import List, Literal, Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import logging
from backend.services.decision_engine import decision_engine
from backend.services.decision_engine import Decision
from backend.services.router_manager import router_manager
from backend.services.osrm import OSRMClient
from backend.services.mapbox_geocoding import MapboxGeocoder
from backend.config import routing_config, RoutingProvider
from backend.services.ml_routing_module import ml_routing_module
from backend.services.h3_routing_module import h3_routing_module
logger = logging.getLogger(__name__)
# Using router_manager for unified routing across all providers
# osrm_client kept for backward compatibility in some endpoints
osrm_client = OSRMClient()
# Initialize Mapbox geocoder for global location support
mapbox_geocoder = MapboxGeocoder(routing_config.mapbox_api_key)



router = APIRouter()


TravelMode = Literal["car", "bike", "walk", "transit"]


class Coordinate(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class RouteLeg(BaseModel):
    start: Coordinate
    end: Coordinate
    distance_meters: float
    duration_seconds: float
    mode: TravelMode
    geometry: str = Field(
        default="",
        description="Encoded polyline string of the route path."
    )


class RouteSummary(BaseModel):
    distance_meters: float
    duration_seconds: float
    estimated_co2_kg: float


class RouteRequest(BaseModel):
    origin: Coordinate
    destination: Coordinate
    mode: TravelMode = "car"
    departure_time: Optional[str] = Field(
        default=None,
        description="ISO8601 timestamp, optional. Used for future real-time integrations.",
    )


class RouteResponse(BaseModel):
    waypoints: List[Coordinate]
    legs: List[RouteLeg]
    summary: RouteSummary
    debug: dict = Field(
        default_factory=dict,
        description="Extra hackathon-friendly debug info.",
    )


class AlternateRouteRequest(RouteRequest):
    event_type: str = Field(
        ...,
        description=(
            "Type of mobility event to consider when suggesting alternates, "
            "e.g. 'road_closure', 'protest', 'concert'."
        ),
    )


class AlternateRouteResponse(BaseModel):
    base_route: RouteResponse
    alternate_route: RouteResponse
    reasoning: str = Field(
        ...,
        description="Human-readable explanation of how events influenced the suggestion.",
    )


def _haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Simple haversine implementation to approximate distance in meters.

    This keeps the demo self-contained without needing external routing APIs.
    """
    r = 6371000  # Earth radius in meters

    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    c = 2 * asin(sqrt(a))
    return r * c


def _estimate_speed_mps(mode: TravelMode) -> float:
    if mode == "walk":
        return 1.4  # ~5 km/h
    if mode == "bike":
        return 4.1  # ~15 km/h
    if mode == "transit":
        return 8.3  # ~30 km/h (averaged)
    return 13.9  # car ~50 km/h urban average


def _estimate_co2_kg(distance_m: float, mode: TravelMode) -> float:
    # Very rough, illustrative values only (kg per km)
    if mode == "walk" or mode == "bike":
        return 0.0
    if mode == "transit":
        factor = 0.08
    else:  # car
        factor = 0.18
    return round((distance_m / 1000.0) * factor, 3)


@router.post("/plan", response_model=RouteResponse, summary="Plan a simple route")
async def plan_route(payload: RouteRequest) -> RouteResponse:
    """
    Plan a simple, single-leg route between two coordinates.
    
    Tries to use MapMyIndia Live Traffic API.
    Falls back to haversine estimation if API is unavailable or fails.
    """
    # 1. Try MapMyIndia API
    mmi_resp = await mmi_client.get_route(
        payload.origin.lat, payload.origin.lon,
        payload.destination.lat, payload.destination.lon,
        payload.mode
    )

    if mmi_resp:
        try:
            # Attempt to parse MapMyIndia response
            # Note: Adjust parsing logic based on actual API response structure
            # This assumes a structure similar to OSRM/Mapbox/Google
            routes = mmi_resp.get("routes", [])
            if routes:
                route = routes[0]
                # Extract distance/duration (often in meters/seconds)
                distance_m = float(route.get("distance", 0))
                duration_s = float(route.get("duration", 0))
                geometry = route.get("geometry", "")
                
                leg = RouteLeg(
                    start=payload.origin,
                    end=payload.destination,
                    distance_meters=round(distance_m, 2),
                    duration_seconds=round(duration_s, 1),
                    mode=payload.mode,
                    geometry=geometry,
                )

                summary = RouteSummary(
                    distance_meters=leg.distance_meters,
                    duration_seconds=leg.duration_seconds,
                    estimated_co2_kg=_estimate_co2_kg(distance_m, payload.mode),
                )

                return RouteResponse(
                    waypoints=[payload.origin, payload.destination],
                    legs=[leg],
                    summary=summary,
                    debug={
                        "implementation": "mapmyindia_live",
                        "note": "Live traffic data used.",
                    },
                )
        except Exception as e:
            logger.error(f"Error parsing MapMyIndia response: {e}")
            # Fall through to fallback

    # 2. Fallback to Haversine
    distance_m = _haversine_distance_m(
        payload.origin.lat,
        payload.origin.lon,
        payload.destination.lat,
        payload.destination.lon,
    )

    speed_mps = _estimate_speed_mps(payload.mode)
    duration_s = distance_m / speed_mps if speed_mps > 0 else 0

    leg = RouteLeg(
        start=payload.origin,
        end=payload.destination,
        distance_meters=round(distance_m, 2),
        duration_seconds=round(duration_s, 1),
        mode=payload.mode,
        geometry="", # No geometry for fallback/haversine
    )

    summary = RouteSummary(
        distance_meters=leg.distance_meters,
        duration_seconds=leg.duration_seconds,
        estimated_co2_kg=_estimate_co2_kg(distance_m, payload.mode),
    )

    return RouteResponse(
        waypoints=[payload.origin, payload.destination],
        legs=[leg],
        summary=summary,
        debug={
            "implementation": "haversine_stub",
            "note": "Fallback used (API unavailable or failed).",
        },
    )


@router.post(
    "/plan/alternate",
    response_model=AlternateRouteResponse,
    summary="Suggest an alternate route based on event type (mocked)",
)
async def plan_alternate_route(
    payload: AlternateRouteRequest,
) -> AlternateRouteResponse:
    """
    Suggest an alternate route based on the type of mobility event.

    Since we don't call real map APIs here, we use simple, transparent
    mock logic:

    - First compute the base route exactly like `/plan`.
    - Then adjust distance and duration by a multiplier that depends
      on `event_type` to simulate detours or slower traffic.
    - We keep the same origin/destination waypoints but clearly explain
      the assumptions in the `reasoning` field.
    """
    base = await plan_route(payload)  # reuse existing logic

    # Mock impact factors by event type
    normalized = payload.event_type.lower().strip()
    if normalized in {"road_closure", "accident", "construction"}:
        factor = 1.3  # 30% longer detour
        reason = (
            "Road closures typically force a detour around the blocked segment, "
            "so we assume about 30% extra distance and time."
        )
    elif normalized in {"protest", "rally", "parade"}:
        factor = 1.2  # slower traffic, mild detour
        reason = (
            "Protests and rallies can slow traffic and partially block streets, "
            "so we assume around 20% extra distance and time."
        )
    elif normalized in {"concert", "sports", "event"}:
        factor = 1.15  # congestion near venue
        reason = (
            "Large events create localized congestion near the venue, so we "
            "assume a 15% increase in distance and travel time for a smarter route."
        )
    else:
        factor = 1.05  # small generic buffer
        reason = (
            "Unknown event type. We apply a small 5% buffer as a conservative "
            "detour estimate while keeping the route close to the base plan."
        )

    alt_distance = round(base.summary.distance_meters * factor, 2)
    alt_duration = round(base.summary.duration_seconds * factor, 1)

    alt_summary = RouteSummary(
        distance_meters=alt_distance,
        duration_seconds=alt_duration,
        estimated_co2_kg=_estimate_co2_kg(alt_distance, payload.mode),
    )

    alt_leg = RouteLeg(
        start=payload.origin,
        end=payload.destination,
        distance_meters=alt_distance,
        duration_seconds=alt_duration,
        mode=payload.mode,
    )

    alternate = RouteResponse(
        waypoints=base.waypoints,
        legs=[alt_leg],
        summary=alt_summary,
        debug={
            "implementation": "event_type_multiplier_stub",
            "event_type": payload.event_type,
            "multiplier": factor,
        },
    )

    return AlternateRouteResponse(
        base_route=base,
        alternate_route=alternate,
        reasoning=reason,
    )


# ============================================================================
# Text-based location routing endpoint
# ============================================================================

class TextRouteRequest(BaseModel):
    source: str = Field(..., description="Starting location name (e.g., 'BTM Layout')")
    destination: str = Field(..., description="Destination location name (e.g., 'MG Road')")
    event: str = Field(
        default="",
        description="Event affecting the route (e.g., 'Political Rally', 'Road Closure')",
    )
    event_location: Optional[Dict[str, float]] = Field(
        default=None,
        description="Coordinates {lat, lon} of the event to avoid"
    )
    event_severity: str = Field(
        default="LOW",
        description="Severity of the event: LOW, MEDIUM, HIGH"
    )
    mode: TravelMode = Field(default="car", description="Travel mode: car, bike, walk, or transit")


class TextRouteResponse(BaseModel):
    recommended_route: str = Field(
        ...,
        description="Human-readable route description with waypoints",
    )
    reason: str = Field(
        ...,
        description="Explanation of why this route was recommended",
    )
    distance_meters: float = Field(..., description="Total distance in meters")
    distance_km: float = Field(..., description="Total distance in kilometers")
    duration_seconds: float = Field(..., description="Estimated travel time in seconds")
    duration_minutes: float = Field(..., description="Estimated travel time in minutes")
    estimated_co2_kg: float = Field(..., description="Estimated CO2 emissions in kg")
    waypoints: List[str] = Field(
        ...,
        description="List of waypoint names in order",
    )
    geometry: str = Field(
        default="",
        description="Encoded polyline of the route"
    )
    detailed_geometry: List[List[float]] = Field(
        default_factory=list,
        description="List of [lat, lon] coordinates for the route path"
    )
    steps: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Turn-by-turn directions"
    )
    start_point: Optional[Dict[str, Any]] = None
    end_point: Optional[Dict[str, Any]] = None
    debug: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Debug information about provider used and fallback status"
    )


async def _geocode_location(location_name: str) -> Dict[str, float]:
    """
    Geocode a location name to coordinates using Mapbox.
    """
    logger.info(f"Geocoding '{location_name}' via Mapbox")
    
    if mapbox_geocoder.is_configured:
        try:
            # Use async geocoding
            result = await mapbox_geocoder.geocode(location_name, country="in")
            
            if result:
                logger.info(f"Successfully geocoded '{location_name}': {result}")
                return result
            else:
                logger.warning(f"Mapbox could not geocode '{location_name}'")
        except Exception as e:
            logger.error(f"Error during Mapbox geocoding: {e}")
            raise HTTPException(status_code=500, detail=f"Geocoding service error: {str(e)}")
    else:
        logger.error("Mapbox geocoder not configured")
        raise HTTPException(status_code=500, detail="Geocoding service not configured")
    
    raise HTTPException(status_code=400, detail=f"Could not find location: '{location_name}'")





@router.post(
    "/suggest",
    response_model=TextRouteResponse,
    summary="Get route suggestion using text-based locations",
)
async def suggest_text_route(payload: TextRouteRequest) -> TextRouteResponse:
    """
    Suggest a route between two text-based locations (e.g., "BTM Layout" to "MG Road").
    
    This endpoint:
    - Accepts location names as strings (not coordinates)
    - Considers events that might affect routing
    - Returns a human-readable route description with waypoints
    - Includes distance, duration, and CO2 estimates
    
    Example request:
    ```json
    {
      "source": "BTM Layout",
      "destination": "MG Road",
      "event": "Political Rally"
    }
    ```
    
    Example response:
    ```json
    {
      "recommended_route": "BTM Layout → JP Nagar → Richmond Road → MG Road",
      "reason": "Avoiding rally congestion near Lalbagh",
      "distance_meters": 6500.0,
      "distance_km": 6.5,
      "duration_seconds": 468.0,
      "duration_minutes": 7.8,
      "estimated_co2_kg": 1.17,
      "waypoints": ["BTM Layout", "JP Nagar", "Richmond Road", "MG Road"]
    }
    ```
    """
    # Geocode source and destination
    source_coords = await _geocode_location(payload.source)
    dest_coords = await _geocode_location(payload.destination)
    
    logger.info(f"Planning route from {payload.source}({source_coords}) to {payload.destination}({dest_coords})")

    # Initialize variables
    waypoints = [source_coords.get("display", payload.source), dest_coords.get("display", payload.destination)]
    reason = "Dynamic Route"
    geometry = ""
    detailed_geometry = []
    steps = []
    distance_m = 0.0
    duration_s = 0.0
    co2_kg = 0.0
    provider_used = "unknown"

    try:
        # Router manager will try providers
        # 1. Fetch Route - Prefer avoidance-capable provider if event is already known
        # This helps consistency by using the same engine for both calls
        initial_pref = RoutingProvider.MAPBOX if payload.event_location else None
        
        # 1. Fetch Route - Decision Engine determines the baseline
        route_resp = await decision_engine.generate_baseline_route(
            source_coords["lat"], source_coords["lon"],
            dest_coords["lat"], dest_coords["lon"],
            payload.mode,
            preferred_provider=initial_pref
        )
        
        should_reroute = False
        initial_provider = route_resp.get("_provider_used") if route_resp else None
        
        # 3. ML-Driven Reaction (Acts only after event is identified)
        if route_resp and payload.event_location and payload.event:
             route_data = route_resp["routes"][0]
             route_geometry = route_data.get("geometry", "")
             
             # Defensive extraction for event_location (might be dict or object)
             ev_loc = payload.event_location
             ev_lat = ev_loc.lat if hasattr(ev_loc, "lat") else ev_loc.get("lat")
             ev_lon = ev_loc.lon if hasattr(ev_loc, "lon") else ev_loc.get("lon")

             event_data = {
                 "type": payload.event,
                 "lat": ev_lat,
                 "lon": ev_lon
             }
             
             # Call H3 module for spatial relevance and detour generation
             # This implements the Uber H3 spatial indexing requirement
             h3_detour = await h3_routing_module.predict_and_reroute(
                 event_data=event_data,
                 source=source_coords,
                 destination=dest_coords,
                 current_geometry=route_geometry,
                 mode=payload.mode,
                 initial_provider=initial_provider
             )
             
             if h3_detour:
                 logger.info("Rerouting using H3-driven spatial alternate.")
                 route_resp = h3_detour
                 provider_used = route_resp.get("_provider_used", initial_provider)
                 reason = f"H3-Detour: Optimized to avoid {payload.event}"
             else:
                 # Fallback to decision engine for standard evaluation if ML doesn't detour
                 evaluation = decision_engine.evaluate_impact(route_geometry, {**event_data, "severity": payload.event_severity})
                 reason = evaluation["reason"]

        # Process the final route response
        if route_resp and route_resp.get("routes"):
            route = route_resp["routes"][0]
            geometry = route.get("geometry", "")
            
            distance_m = float(route.get("distance", 0))
            duration_s = float(route.get("duration", 0))
            
            # Extract steps for turn-by-turn
            legs = route.get("legs", [])
            for leg in legs:
                steps.extend(leg.get("steps", []))
            
            provider_used = route_resp.get("_provider_used", "unknown")
            logger.info(f"Route calculated using provider: {provider_used}")
            
            # Decode geometry if needed
            if geometry:
                from backend.utils.geometry import decode_polyline
                try:
                    detailed_geometry = decode_polyline(geometry)
                except Exception as ex:
                    logger.warning(f"Failed to decode polyline: {ex}")
        
    except Exception as e:
        logger.error(f"Routing API error: {e}")
        # Don't silence the error unless we really have a fallback
        raise HTTPException(status_code=502, detail=f"Routing provider failed: {str(e)}")

    if not geometry:
        logger.error("Failed to generate route geometry.")
        raise HTTPException(status_code=502, detail="Route generation failed. Please check inputs.")
    
    # Calculate CO2
    co2_kg = _estimate_co2_kg(distance_m, payload.mode)
    
    route_str = f"{payload.source} → {payload.destination}"
    
    return TextRouteResponse(
        recommended_route=route_str,
        reason=reason,
        distance_meters=round(distance_m, 2),
        distance_km=round(distance_m / 1000.0, 2),
        duration_seconds=round(duration_s, 1),
        duration_minutes=round(duration_s / 60.0, 1),
        estimated_co2_kg=co2_kg,
        waypoints=waypoints,
        geometry=geometry,
        detailed_geometry=detailed_geometry,
        steps=steps,
        start_point=source_coords,
        end_point=dest_coords,
        debug={
            "provider_used": provider_used,
            "source_coords": source_coords,
            "dest_coords": dest_coords,
            "event_active": bool(payload.event)
        }
    )

@router.post(
    "/recalculate",
    response_model=TextRouteResponse,
    summary="Recalculate route based on current coordinates and new event data",
)
async def recalculate_route(payload: TextRouteRequest) -> TextRouteResponse:
    """
    Simulates a dynamic recalculation. 
    In a real system, this might be triggered by a geofence or traffic event.
    """
    return await suggest_text_route(payload)


@router.get(
    "/providers/status",
    summary="Get routing provider configuration status",
)
async def get_provider_status() -> Dict[str, Any]:
    """
    Get status of all routing providers for debugging and monitoring.
    
    Returns information about:
    - Which providers are configured (have valid API keys)
    - Preferred provider setting
    - Fallback chain order
    - Provider requirements
    
    This endpoint is useful for:
    - Verifying API key configuration
    - Debugging routing issues
    - Monitoring provider availability
    
    Note: API keys are NEVER exposed in the response.
    """
    return router_manager.get_provider_status()
