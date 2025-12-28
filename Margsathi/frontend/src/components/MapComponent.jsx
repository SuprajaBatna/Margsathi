import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for default marker icons in Leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Helper to decode OSRM/MapMyIndia encoded polyline
// MMI uses precision 6 by default for 'polyline6'
function decodePolyline(encoded, precision = 6) {
    if (!encoded) return [];
    var points = [];
    var index = 0, len = encoded.length;
    var lat = 0, lng = 0;
    const factor = Math.pow(10, precision);

    while (index < len) {
        var b, shift = 0, result = 0;
        do {
            b = encoded.charCodeAt(index++) - 63;
            result |= (b & 0x1f) << shift;
            shift += 5;
        } while (b >= 0x20);
        var dlat = ((result & 1) ? ~(result >> 1) : (result >> 1));
        lat += dlat;
        shift = 0;
        result = 0;
        do {
            b = encoded.charCodeAt(index++) - 63;
            result |= (b & 0x1f) << shift;
            shift += 5;
        } while (b >= 0x20);
        var dlng = ((result & 1) ? ~(result >> 1) : (result >> 1));
        lng += dlng;
        points.push([lat / factor, lng / factor]);
    }
    return points;
}

const MapComponent = ({ startPoint, endPoint, geometry, detailedGeometry, steps, activeStepIndex, onStepClick, simulatedEvent, isCalculating }) => {
    const mapRef = useRef(null);
    const mapInstance = useRef(null);
    const markersRef = useRef([]);
    const polylineRef = useRef(null);
    const polylineGlowRef = useRef(null);
    const stepMarkerRef = useRef(null);
    const eventMarkerRef = useRef(null);
    const recenterControlRef = useRef(null);

    // Rerouting state
    const previousGeometryRef = useRef(null);
    const oldPolylineRef = useRef(null);
    const oldPolylineGlowRef = useRef(null);
    const isReroutingRef = useRef(false);

    // Custom Icons setup
    const createCustomIcon = (type) => {
        const color = type === 'start' ? '#22c55e' : type === 'end' ? '#ef4444' : '#3b82f6';
        const isStep = type === 'step';
        const svg = `
            <svg width="${isStep ? '24' : '32'}" height="${isStep ? '24' : '32'}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2C8.13 2 5 5.13 5 9C5 14.25 12 22 12 22C12 22 19 14.25 19 9C19 5.13 15.87 2 12 2Z" fill="${color}" stroke="white" stroke-width="2"/>
                <circle cx="12" cy="9" r="3" fill="white"/>
            </svg>
        `;
        return L.divIcon({
            html: svg,
            className: 'custom-marker-icon',
            iconSize: isStep ? [24, 24] : [32, 32],
            iconAnchor: isStep ? [12, 24] : [16, 32],
            popupAnchor: [0, -32]
        });
    };

    const createPulseIcon = () => {
        const svg = `
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="20" cy="20" r="8" fill="#3b82f6" fill-opacity="0.3">
                    <animate attributeName="r" from="8" to="20" dur="1.5s" repeatCount="indefinite" />
                    <animate attributeName="fill-opacity" from="0.3" to="0" dur="1.5s" repeatCount="indefinite" />
                </circle>
                <circle cx="20" cy="20" r="6" fill="#3b82f6" stroke="white" stroke-width="2"/>
            </svg>
        `;
        return L.divIcon({
            html: svg,
            className: 'pulse-marker-icon',
            iconSize: [40, 40],
            iconAnchor: [20, 20]
        });
    };

    const createEventIcon = () => {
        const svg = `
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="10" fill="#dc2626" fill-opacity="0.2">
                    <animate attributeName="r" from="10" to="20" dur="2s" repeatCount="indefinite" />
                    <animate attributeName="fill-opacity" from="0.2" to="0" dur="2s" repeatCount="indefinite" />
                </circle>
                <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" fill="#dc2626" stroke="white" stroke-width="2"/>
            </svg>
        `;
        return L.divIcon({
            html: svg,
            className: 'event-marker-icon',
            iconSize: [40, 40],
            iconAnchor: [20, 20],
            popupAnchor: [0, -20]
        });
    };

    useEffect(() => {
        // Initialize map if not exists
        if (!mapInstance.current && mapRef.current) {
            mapInstance.current = L.map(mapRef.current, {
                zoomControl: false,
                attributionControl: false
            }).setView([12.9716, 77.5946], 13);

            L.control.zoom({ position: 'bottomright' }).addTo(mapInstance.current);

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap'
            }).addTo(mapInstance.current);

            L.control.attribution({ prefix: false }).addAttribution('Margsathi Navigation').addTo(mapInstance.current);

            // Add custom Recenter control
            const RecenterControl = L.Control.extend({
                onAdd: function () {
                    const btn = L.DomUtil.create('button', 'leaflet-bar leaflet-control leaflet-control-custom');
                    btn.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 3 21 3 21 9"></polyline><polyline points="9 21 3 21 3 15"></polyline><line x1="21" y1="3" x2="14" y2="10"></line><line x1="3" y1="21" x2="10" y2="14"></line></svg>';
                    btn.style.backgroundColor = 'white';
                    btn.style.width = '34px';
                    btn.style.height = '34px';
                    btn.style.display = 'flex';
                    btn.style.alignItems = 'center';
                    btn.style.justifyContent = 'center';
                    btn.style.cursor = 'pointer';
                    btn.title = "Recenter Route";

                    btn.onclick = function () {
                        if (polylineRef.current) {
                            mapInstance.current.fitBounds(polylineRef.current.getBounds(), { padding: [50, 50], animate: true });
                        }
                    };
                    return btn;
                }
            });
            recenterControlRef.current = new RecenterControl({ position: 'bottomright' }).addTo(mapInstance.current);
        }

        return () => {
            if (mapInstance.current) {
                mapInstance.current.remove();
                mapInstance.current = null;
            }
        };
    }, []);

    useEffect(() => {
        if (!mapInstance.current) return;

        const isEventActive = !!simulatedEvent;

        // Detect rerouting: geometry changed but we have a previous route
        const currentGeometry = geometry || (detailedGeometry && detailedGeometry.length > 0 ? JSON.stringify(detailedGeometry) : null);
        const isRerouting = previousGeometryRef.current && currentGeometry && previousGeometryRef.current !== currentGeometry;

        if (isRerouting) {
            console.log('🔄 Rerouting detected!');
            isReroutingRef.current = true;

            // Keep old route visible temporarily with fade effect
            if (polylineRef.current) {
                oldPolylineRef.current = polylineRef.current;
                oldPolylineGlowRef.current = polylineGlowRef.current;

                // Fade out old route
                const fadeDelay = isEventActive ? 0 : 100; // Immediate removal if it's an event detour
                const removeDelay = isEventActive ? 50 : 1500;

                setTimeout(() => {
                    if (oldPolylineRef.current) {
                        oldPolylineRef.current.setStyle({ opacity: 0.3, color: '#9ca3af' });
                    }
                    if (oldPolylineGlowRef.current) {
                        oldPolylineGlowRef.current.setStyle({ opacity: 0.1 });
                    }
                }, fadeDelay);

                // Remove old route after animation
                setTimeout(() => {
                    if (oldPolylineRef.current) {
                        oldPolylineRef.current.remove();
                        oldPolylineRef.current = null;
                    }
                    if (oldPolylineGlowRef.current) {
                        oldPolylineGlowRef.current.remove();
                        oldPolylineGlowRef.current = null;
                    }
                }, removeDelay);
            }
        } else {
            // Clear existing elements normally
            if (polylineRef.current) {
                polylineRef.current.remove();
                polylineRef.current = null;
            }
            if (polylineGlowRef.current) {
                polylineGlowRef.current.remove();
                polylineGlowRef.current = null;
            }
        }

        // Clear markers and step markers
        markersRef.current.forEach(m => m.remove());
        markersRef.current = [];
        if (stepMarkerRef.current) {
            stepMarkerRef.current.remove();
            stepMarkerRef.current = null;
        }
        if (eventMarkerRef.current) {
            eventMarkerRef.current.remove();
            eventMarkerRef.current = null;
        }

        const positions = [];

        // Add start marker
        if (startPoint && startPoint.lat && startPoint.lon) {
            const pos = [startPoint.lat, startPoint.lon];
            const m = L.marker(pos, { icon: createCustomIcon('start') })
                .bindPopup(`< b > Start</b > <br />${startPoint.display || 'Origin'} `)
                .addTo(mapInstance.current);
            markersRef.current.push(m);
            positions.push(pos);
        }

        // Add end marker
        if (endPoint && endPoint.lat && endPoint.lon) {
            const pos = [endPoint.lat, endPoint.lon];
            const m = L.marker(pos, { icon: createCustomIcon('end') })
                .bindPopup(`< b > Destination</b > <br />${endPoint.display || 'Destination'} `)
                .addTo(mapInstance.current);
            markersRef.current.push(m);
            positions.push(pos);
        }

        // Determine route coordinates
        let route = [];
        if (detailedGeometry && detailedGeometry.length > 0) {
            route = detailedGeometry;
        } else if (geometry) {
            route = decodePolyline(geometry, 6);
        }

        // Render premium polyline
        // Color logic: 
        // - Rerouting: Bright green temporarily, then transition to normal
        // - Event active: Light Brown
        // - Normal: Blue
        const isReroutingNow = isReroutingRef.current;

        let mainColor, glowColor;
        if (isReroutingNow) {
            mainColor = '#10b981'; // Bright green for pulse transition
            glowColor = '#059669';
        } else if (isEventActive && isCalculating) {
            mainColor = '#D2691E'; // Impacted route is BROWN
            glowColor = '#8B4513';
        } else {
            mainColor = '#3b82f6'; // Initial and Detour are BLUE
            glowColor = '#1e40af';
        }

        console.log(`🗺️ Rendering Polyline.Points: ${route.length}, Rerouting: ${isReroutingNow}, Processing: ${isCalculating} `);

        if (route.length > 0) {
            // Add new glow/shadow first
            polylineGlowRef.current = L.polyline(route, {
                color: glowColor,
                weight: 12,
                opacity: isReroutingNow ? 0.3 : 0.15,
                lineJoin: 'round'
            }).addTo(mapInstance.current);

            // Add main polyline
            polylineRef.current = L.polyline(route, {
                color: mainColor,
                weight: isReroutingNow ? 8 : 6,
                opacity: 0.9,
                lineJoin: 'round',
                lineCap: 'round',
                className: (isEventActive || isReroutingNow) ? 'polyline-pulse' : ''
            }).addTo(mapInstance.current);

            // Transition reroute color back to normal after delay
            if (isReroutingNow) {
                setTimeout(() => {
                    const finalColor = isEventActive ? '#D2691E' : '#3b82f6';
                    const finalGlow = isEventActive ? '#8B4513' : '#1e40af';

                    if (polylineRef.current) {
                        polylineRef.current.setStyle({
                            color: finalColor,
                            weight: 6
                        });
                    }
                    if (polylineGlowRef.current) {
                        polylineGlowRef.current.setStyle({
                            color: finalGlow,
                            opacity: 0.15
                        });
                    }
                    isReroutingRef.current = false;
                }, 2000);
            }

            positions.push(...route);
        } else {
            console.warn("⚠️ Route geometry is empty!");
        }

        // Auto-fit map bounds (always recenter on reroute or init)
        if (positions.length > 0) {
            const bounds = L.latLngBounds(positions);
            // Always fit bounds when route updates to ensure visibility
            // Always fit bounds when route updates to ensure visibility
            console.log("Adjusting map bounds");
            mapInstance.current.fitBounds(bounds, {
                padding: [50, 50],
                maxZoom: 16,
                animate: true,
                duration: 1.5
            });
        }

        // Update previous geometry reference
        previousGeometryRef.current = currentGeometry;


        // Add Simulated Event Marker
        if (simulatedEvent && simulatedEvent.lat && simulatedEvent.lon) {
            const pos = [simulatedEvent.lat, simulatedEvent.lon];
            eventMarkerRef.current = L.marker(pos, { icon: createEventIcon() })
                .bindPopup(`
    < div class="p-2" >
                        <div class="font-bold text-red-600 flex items-center gap-2">
                            ⚠️ Event Detected
                        </div>
                        <div class="text-sm font-medium mt-1">${simulatedEvent.event_name}</div>
                        <div class="text-xs text-gray-500 mt-1">Severity: ${simulatedEvent.severity}</div>
                    </div >
    `, { closeButton: false })
                .addTo(mapInstance.current);

            // Auto open popup
            eventMarkerRef.current.openPopup();
        }
    }, [startPoint, endPoint, geometry, detailedGeometry, simulatedEvent, isCalculating]);

    // Handle Active Step Zoom
    useEffect(() => {
        if (!mapInstance.current || activeStepIndex === null || !steps || !steps[activeStepIndex]) return;

        const step = steps[activeStepIndex];
        let lat, lon;

        if (step.location) {
            [lat, lon] = step.location;
        } else if (step.maneuver && step.maneuver.location) {
            [lon, lat] = step.maneuver.location; // OSRM often uses [lon, lat]
        }

        if (lat && lon) {
            // Remove previous step marker
            if (stepMarkerRef.current) {
                stepMarkerRef.current.remove();
            }

            // Fly to location
            mapInstance.current.flyTo([lat, lon], 17, {
                animate: true,
                duration: 1
            });

            // Add highlight marker
            stepMarkerRef.current = L.marker([lat, lon], {
                icon: createPulseIcon(),
                zIndexOffset: 1000
            })
                .addTo(mapInstance.current);
        }
    }, [activeStepIndex, steps]);

    return (
        <div className="relative w-full h-full">
            <div
                ref={mapRef}
                style={{ height: '100%', width: '100%' }}
                className="z-0"
            />
            {/* Custom overlay glassmorphism for map info if needed */}
            <div className="absolute bottom-4 left-4 z-[400] bg-white/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/40 shadow-sm text-[10px] text-gray-500 font-medium">
                Real-time Route Geometry Enabled
            </div>
        </div>
    );
};

export default MapComponent;
