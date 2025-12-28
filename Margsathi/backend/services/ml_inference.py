"""
ML Inference Service

Simulates a Machine Learning inference engine for detecting traffic events
from unstructured (image/video feed) or structured (sensor) data.

This service is designed to be independent of the routing logic.
"""

import random
import time
from typing import Dict, Any, Optional, List
from enum import Enum
from pydantic import BaseModel

class TrafficEventType(str, Enum):
    ACCIDENT = "Accident"
    CONGESTION = "Congestion"
    CROWD = "Crowd"
    CLEAR = "Clear"
    CONSTRUCTION = "Construction"
    ROADBLOCK = "Roadblock"
    RALLY = "Rally"
    POLITICAL_MEETING = "Political meeting"
    ROAD_CONSTRUCTION = "Road construction"

class InferenceResult(BaseModel):
    event_type: TrafficEventType
    confidence: float
    lat: Optional[float] = None
    lon: Optional[float] = None
    processing_time_ms: float
    timestamp: float

class TrafficEventDetector:
    """
    Simulated ML Inference Engine for Traffic Event Detection.
    """
    
    def __init__(self, model_version: str = "v1.0.0"):
        self.model_version = model_version
        # In a real scenario, load PyTorch/TF model here
        self._is_ready = True

    def predict(self, input_data: Dict[str, Any]) -> InferenceResult:
        """
        Perform inference on input data.
        
        Args:
            input_data: Dict containing 'type' ('image', 'sensor') and content.
                        e.g., {'type': 'image', 'path': '/tmp/feed_001.jpg', 'lat': ..., 'lon': ...}
        
        Returns:
            InferenceResult object
        """
        start_time = time.time()
        
        input_type = input_data.get("type", "unknown")
        
        if input_type == "image":
            result = self._simulate_vision_inference(input_data)
        elif input_type == "sensor":
            result = self._rule_based_inference(input_data)
        else:
            # Default fallback
            result = {
                "event_type": TrafficEventType.CLEAR,
                "confidence": 0.99
            }
            
        processing_time = (time.time() - start_time) * 1000
        
        return InferenceResult(
            event_type=result["event_type"],
            confidence=result["confidence"],
            lat=input_data.get("lat"),
            lon=input_data.get("lon"),
            processing_time_ms=round(processing_time, 2),
            timestamp=start_time
        )

    def _simulate_vision_inference(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate a Computer Vision model prediction.
        Refurns random events based on a 'seed' or completely random if not provided.
        """
        # Simulate processing delay
        time.sleep(random.uniform(0.05, 0.2))
        
        # If input has 'force_event' (for testing/demo), use it
        if "force_event" in data:
            fe = data["force_event"]
            try:
                # Try direct match
                return {
                    "event_type": TrafficEventType(fe),
                    "confidence": random.uniform(0.85, 0.98)
                }
            except ValueError:
                # Fuzzy mapping for demo robustness
                mapping = {
                    "Rally": TrafficEventType.RALLY,
                    "Political meeting": TrafficEventType.POLITICAL_MEETING,
                    "Road construction": TrafficEventType.ROAD_CONSTRUCTION,
                    "Road Closure": TrafficEventType.ROADBLOCK,
                    "Accident": TrafficEventType.ACCIDENT
                }
                etype = mapping.get(fe, TrafficEventType.CONGESTION)
                return {
                    "event_type": etype,
                    "confidence": random.uniform(0.85, 0.98)
                }
            
        # Random simulation
        val = random.random()
        if val < 0.7:
            return {"event_type": TrafficEventType.CLEAR, "confidence": random.uniform(0.8, 0.99)}
        elif val < 0.8:
            return {"event_type": TrafficEventType.CONGESTION, "confidence": random.uniform(0.7, 0.9)}
        elif val < 0.9:
            return {"event_type": TrafficEventType.ACCIDENT, "confidence": random.uniform(0.6, 0.85)}
        else:
            return {"event_type": TrafficEventType.CROWD, "confidence": random.uniform(0.75, 0.9)}

    def _rule_based_inference(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simple classifier for structured sensor data (Speed, Density).
        """
        speed = data.get("avg_speed_kmh", 60)
        density = data.get("vehicle_density", 10) # vehicles per km
        
        if speed < 10 and density > 80:
            return {"event_type": TrafficEventType.CONGESTION, "confidence": 0.95}
        elif speed < 5:
            # Suspiciously low speed but low density? Maybe accident blocking flow?
            return {"event_type": TrafficEventType.ACCIDENT, "confidence": 0.65}
        elif density > 100:
            return {"event_type": TrafficEventType.CROWD, "confidence": 0.88}
        
        return {"event_type": TrafficEventType.CLEAR, "confidence": 0.9}

# Singleton export
traffic_detector = TrafficEventDetector()
