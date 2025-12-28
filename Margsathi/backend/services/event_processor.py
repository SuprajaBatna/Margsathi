"""
Event Processor Service

Orchestrates the flow between ML Inference and Decision Logic.
Ensures loose coupling by acting as a bridge.

Flow:
1. Receive raw input (image/sensor)
2. Get ML Prediction
3. Filter by Confidence
4. Evaluate Impact via Decision Engine
"""

import logging
from typing import Dict, Any, Optional, Union, List

from backend.services.ml_inference import traffic_detector, TrafficEventType
from backend.services.decision_engine import decision_engine, Decision

# Configure logger
logger = logging.getLogger(__name__)

class EventProcessor:
    """
    Bridge between ML Inference and Routing Decision logic.
    """
    
    def __init__(self, confidence_threshold: float = 0.75):
        self.confidence_threshold = confidence_threshold

    def process_input_for_route(
        self,
        ml_input: Dict[str, Any],
        route_geometry: Union[str, List[List[float]]],
        current_metrics: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Process raw input against a specific route to determine if rerouting is needed.
        
        Args:
            ml_input: Data for ML service (image path or sensor data)
            route_geometry: Polyline of the current active route
            current_metrics: Optional current distance/duration
            
        Returns:
            Dict with 'action' (REROUTE/CONTINUE) and 'metadata'
        """
        logger.info(f"Processing ML input for route analysis. Type: {ml_input.get('type')}")
        
        # 1. ML Inference
        prediction = traffic_detector.predict(ml_input)
        logger.info(f"ML Prediction: {prediction.event_type} (Conf: {prediction.confidence:.2f})")
        
        # KEY: If we don't have location data in ML input (e.g. raw image), 
        # we can't really check "on route" without context.
        # For this loosely coupled design, we assume the input MIGHT have location metadata
        # or the ML model infers it.
        # If lat/lon provided in input, we use that.
        event_lat = prediction.lat or ml_input.get("lat")
        event_lon = prediction.lon or ml_input.get("lon")
        
        if not event_lat or not event_lon:
            return {
                "action": Decision.CONTINUE,
                "reason": "No location data associated with ML event",
                "ml_result": prediction.dict()
            }

        # 2. Confidence Threshold Check
        if prediction.confidence < self.confidence_threshold:
            logger.info(f"Event ignored: Low confidence ({prediction.confidence:.2f} < {self.confidence_threshold})")
            return {
                "action": Decision.CONTINUE,
                "reason": "Low ML confidence",
                "ml_result": prediction.dict()
            }
            
        if prediction.event_type == TrafficEventType.CLEAR:
             return {
                "action": Decision.CONTINUE,
                "reason": "Traffic detected as CLEAR",
                "ml_result": prediction.dict()
            }

        # 3. Construct Event Data for Decision Engine
        # Map ML type to Decision Engine expectation
        # ML: TrafficEventType -> string
        severity_map = {
            TrafficEventType.ACCIDENT: "HIGH",
            TrafficEventType.CONGESTION: "MEDIUM", # Depends. Let's say high density = HIGH? 
            # Simple mapping for now
            TrafficEventType.CROWD: "MEDIUM",
            TrafficEventType.CONSTRUCTION: "HIGH",
            TrafficEventType.ROADBLOCK: "HIGH"
        }
        
        severity = severity_map.get(prediction.event_type, "LOW")
        
        event_data = {
            "type": prediction.event_type.value,
            "severity": severity,
            "lat": event_lat,
            "lon": event_lon,
            "radius": 500 # Default impact radius
        }
        
        # 4. Decision Engine Evaluation
        decision_result = decision_engine.evaluate_impact(route_geometry, event_data, current_metrics)
        
        logger.info(f"Decision Engine Result: {decision_result['decision']} - {decision_result['reason']}")
        
        return {
            "action": decision_result["decision"],
            "reason": decision_result["reason"],
            "details": decision_result["details"],
            "ml_result": prediction.dict()
        }

# Singleton
event_processor = EventProcessor()
