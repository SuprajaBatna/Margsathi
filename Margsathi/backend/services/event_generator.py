"""
Mock Event Generator Service

Generates simulated traffic events for testing routing logic.
"""

import random
from typing import List, Dict, Optional, Literal
from enum import Enum
import time

class EventSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class EventType(str, Enum):
    ACCIDENT = "Accident"
    CONGESTION = "Congestion"
    ROADBLOCK = "Roadblock"
    RALLY = "Rally"
    CONSTRUCTION = "Construction"

class MockEventGenerator:
    """
    Generates simulated traffic events.
    Key features:
    - Toggle ON/OFF
    - Randomized event types and severity
    - Location-aware generation (optional)
    """
    
    def __init__(self):
        self.is_enabled = True
        self.active_events: List[Dict] = []
        
    def toggle(self, enable: bool) -> bool:
        """Enable or disable event generation."""
        self.is_enabled = enable
        return self.is_enabled

    def generate_event_near(
        self, 
        lat: float, 
        lon: float, 
        radius_km: float = 0.5
    ) -> Optional[Dict]:
        """
        Generate a random event near a specific location.
        Returns None if generator is disabled.
        """
        if not self.is_enabled:
            return None

        # Random offset within radius (approximate)
        # 1 deg lat ~= 111km, 1 deg lon ~= 111km * cos(lat)
        # 0.5km is roughly 0.0045 degrees
        offset_lat = random.uniform(-0.0045, 0.0045)
        offset_lon = random.uniform(-0.0045, 0.0045)

        event_type = random.choice(list(EventType))
        severity = self._determine_severity(event_type)

        event = {
            "event_id": f"evt_{int(time.time()*1000)}",
            "event_type": event_type.value,
            "severity": severity.value,
            "lat": round(lat + offset_lat, 6),
            "lon": round(lon + offset_lon, 6),
            "timestamp": time.time(),
            "description": f"{severity.value} severity {event_type.value} reported."
        }
        
        self.active_events.append(event)
        return event

    def _determine_severity(self, event_type: EventType) -> EventSeverity:
        """Assign severity probability based on event type."""
        if event_type in [EventType.ACCIDENT, EventType.ROADBLOCK]:
            # Higher chance of High severity
            return random.choice([EventSeverity.MEDIUM, EventSeverity.HIGH, EventSeverity.HIGH])
        elif event_type == EventType.RALLY:
            return EventSeverity.HIGH
        else:
            return random.choice(list(EventSeverity))

# Global instance
event_generator = MockEventGenerator()
