import { useState, useEffect } from 'react'
import { MapPin, Navigation, Clock, Leaf, Loader2, Menu, X } from 'lucide-react'
import axios from 'axios'
import MapComponent from '../components/MapComponent'

const Routing = () => {
  console.log("Routing Component Rendered")
  const [source, setSource] = useState('')
  const [destination, setDestination] = useState('')
  const [event, setEvent] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const [activeStepIndex, setActiveStepIndex] = useState(null)
  const [isLiveEnabled, setIsLiveEnabled] = useState(false)
  const [lastCalculated, setLastCalculated] = useState(null)
  const [simulatedEvent, setSimulatedEvent] = useState(null)
  const [showNotification, setShowNotification] = useState(false)

  // Reroute tracking
  const [previousResult, setPreviousResult] = useState(null)
  const [isRerouting, setIsRerouting] = useState(false)
  const [etaChanged, setEtaChanged] = useState(false)
  const [distanceChanged, setDistanceChanged] = useState(false)

  const eventTypes = [
    { value: '', label: 'No Event' },
    { value: 'Road Closure', label: 'Road Closure' },
    { value: 'Political Rally', label: 'Political Rally' },
    { value: 'Protest', label: 'Protest' },
    { value: 'Concert', label: 'Concert' },
    { value: 'Accident', label: 'Accident' },
    { value: 'Construction', label: 'Construction' },
  ]

  const handleSubmit = async (e, eventLocation = null) => {
    if (e && e.preventDefault) e.preventDefault()
    setLoading(true)
    setError(null)
    setActiveStepIndex(null)

    try {
      // Use passed event details if available (fixes race condition), otherwise fallback to state
      const effectiveEvent = eventLocation || simulatedEvent;

      const payload = {
        source,
        destination,
        event: effectiveEvent ? (effectiveEvent.event_name || 'Accident') : event,
        mode: 'car',
        provider: result?._provider_used || null, // Stick to previous provider if available
        event_severity: effectiveEvent ? effectiveEvent.severity : 'LOW',
      }

      // If effective event exists, send its location for avoidance
      if (effectiveEvent) {
        payload.event_location = { lat: effectiveEvent.lat, lon: effectiveEvent.lon }
      }

      console.log('🚀 Initiating Route Request:', {
        source,
        destination,
        event,
        isReroute: !!effectiveEvent,
        timestamp: new Date().toISOString()
      });

      const response = await axios.post('/api/routing/suggest', payload)

      setResult(response.data)
      setLastCalculated(new Date().toLocaleTimeString())
      setIsSidebarOpen(true) // Keep sidebar open to show results

      // Detect rerouting
      if (previousResult && previousResult.geometry !== response.data.geometry) {
        console.log('🔄 Reroute detected in Routing.jsx');
        setIsRerouting(true);

        // Check if ETA or distance changed
        if (previousResult.duration_minutes !== response.data.duration_minutes) {
          setEtaChanged(true);
          setTimeout(() => setEtaChanged(false), 3000);
        }
        if (previousResult.distance_km !== response.data.distance_km) {
          setDistanceChanged(true);
          setTimeout(() => setDistanceChanged(false), 3000);
        }

        // Reset rerouting flag after animation
        setTimeout(() => setIsRerouting(false), 3000);
      }

      // Store current result as previous for next comparison
      setPreviousResult(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to get route suggestion')
    } finally {
      setLoading(false)
    }
  }

  // Auto-recalculate on source/destination change (Debounced)
  useEffect(() => {
    if (!source || !destination) return
    // Reset simulation on new inputs
    setSimulatedEvent(null)
    setEvent('')
    setShowNotification(false)

    const timer = setTimeout(() => {
      // Avoid re-fetching if result already matches current inputs
      if (source !== result?.start_point?.display || destination !== result?.end_point?.display) {
        handleSubmit({ preventDefault: () => { } })
      }
    }, 2500)
    return () => clearTimeout(timer)
  }, [source, destination])

  // Polling Simulation for Traffic/Events
  useEffect(() => {
    if (!isLiveEnabled || !result) return

    const pollInterval = setInterval(async () => {
      console.log("Polling for dynamic updates...")
      // Simulate external traffic detection
      const randomTrigger = Math.random() > 0.8
      if (randomTrigger) {
        const mockEvents = ['Rally', 'Political meeting', 'Road construction']
        const randomEvent = mockEvents[Math.floor(Math.random() * mockEvents.length)]
        setEvent(randomEvent)
        // Recalculation will be triggered by the 'event' useEffect
      }
    }, 12000)

    return () => clearInterval(pollInterval)
  }, [isLiveEnabled, !!result])

  // State to track if simulation has already run for the current result
  const [hasSimulatedThisSession, setHasSimulatedThisSession] = useState(false);

  // Reset simulation flag when source/destination changes
  useEffect(() => {
    setHasSimulatedThisSession(false);
  }, [source, destination]);

  // Event Simulation Logic
  useEffect(() => {
    // Only trigger if we have a result, no active event, and hasn't simulated yet
    if (result && !event && !simulatedEvent && !loading && !hasSimulatedThisSession) {
      console.log("Starting event simulation timer (10s)...")

      const timer = setTimeout(() => {
        console.log("Simulating Event!")
        setHasSimulatedThisSession(true);

        // 1. Pick a location along the route
        let eventLocation = null

        if (result.detailed_geometry && result.detailed_geometry.length > 10) {
          const minIdx = Math.floor(result.detailed_geometry.length * 0.3);
          const maxIdx = Math.floor(result.detailed_geometry.length * 0.7);
          const randomIdx = Math.floor(Math.random() * (maxIdx - minIdx + 1)) + minIdx;
          const point = result.detailed_geometry[randomIdx];
          if (Array.isArray(point)) {
            eventLocation = { lat: point[0], lon: point[1] };
          }
        }

        if (!eventLocation && result.end_point) {
          eventLocation = { lat: result.end_point.lat - 0.001, lon: result.end_point.lon - 0.001 }
        }

        if (eventLocation) {
          // 2. Create Mock Event - Types: Rally, Political meeting, Road construction
          const mockEventTypes = ['Rally', 'Political meeting', 'Road construction'];
          const selectedLabel = mockEventTypes[Math.floor(Math.random() * mockEventTypes.length)];

          const mockEvent = {
            event_id: `evt_${Date.now()}`,
            event_name: selectedLabel,
            severity: 'HIGH',
            lat: eventLocation.lat,
            lon: eventLocation.lon,
            affected_radius: 500
          }

          // 3. Update State
          setSimulatedEvent(mockEvent)
          setShowNotification(true)

          // 4. Trigger Recalculation
          setEvent(selectedLabel)
          handleSubmit({ preventDefault: () => { } }, mockEvent)
        }
      }, 10000)

      return () => clearTimeout(timer)
    }
  }, [result, event, simulatedEvent, loading, hasSimulatedThisSession])

  // Trigger recalculate when event changes is handled by explicit call in simulation effect
  // We can keep this for manual event changes if needed, but avoid double calling
  useEffect(() => {
    if (event && result && !simulatedEvent) {
      handleSubmit({ preventDefault: () => { } })
    }
  }, [event])

  return (
    <div className="relative h-[calc(100vh-64px)] w-full overflow-hidden flex flex-col md:flex-row bg-gray-50">
      {/* Sidebar Controls / Bottom Sheet */}
      <div
        className={`fixed md:relative z-40 md:z-10 bottom-0 md:top-0 left-0 w-full md:w-96 bg-white shadow-2xl md:shadow-xl transition-all duration-500 ease-in-out flex flex-col
          ${isSidebarOpen
            ? 'h-[85vh] md:h-full translate-y-0'
            : 'h-16 md:h-full translate-y-[calc(85vh-4rem)] md:translate-x-0'}
          ${!isSidebarOpen && 'md:w-96'}
        `}
      >
        <div
          className="p-4 border-b border-gray-200 flex justify-between items-center bg-primary-600 text-white cursor-pointer md:cursor-default lg:rounded-t-none rounded-t-2xl md:rounded-t-none"
          onClick={() => window.innerWidth < 768 && setIsSidebarOpen(!isSidebarOpen)}
        >
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Navigation className="w-6 h-6" />
            <span className="hidden md:inline">Plan Your Route</span>
            <span className="md:hidden">{result ? 'Route Details' : 'Plan Your Route'}</span>
          </h1>
          <div className="flex items-center gap-2">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setIsSidebarOpen(!isSidebarOpen);
              }}
              className="p-1 hover:bg-primary-700 rounded transition-colors"
            >
              {isSidebarOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>

        <div className={`flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar ${!isSidebarOpen && 'hidden md:block'}`}>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="relative">
              <MapPin className="absolute left-3 top-3 w-5 h-5 text-gray-400" />
              <input
                type="text"
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition-all"
                placeholder="Starting Point (e.g., BTM Layout)"
                value={source}
                onChange={(e) => setSource(e.target.value)}
                required
              />
            </div>

            <div className="relative">
              <Navigation className="absolute left-3 top-3 w-5 h-5 text-gray-400" />
              <input
                type="text"
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition-all"
                placeholder="Destination (e.g., MG Road)"
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Event (Optional)</label>
              <select
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none"
                value={event}
                onChange={(e) => setEvent(e.target.value)}
              >
                {eventTypes.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>

            <button
              type="submit"
              className="w-full bg-primary-600 hover:bg-primary-700 text-white py-3 rounded-lg font-semibold flex items-center justify-center space-x-2 transition-colors shadow-sm"
              disabled={loading}
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Calculating...</span>
                </>
              ) : (
                <>
                  <Navigation className="w-5 h-5" />
                  <span>Get Directions</span>
                </>
              )}
            </button>

            <div className="flex items-center justify-between pt-2 border-t border-gray-100 pt-4">
              <label className="flex items-center cursor-pointer group">
                <div className="relative">
                  <input
                    type="checkbox"
                    className="sr-only"
                    checked={isLiveEnabled}
                    onChange={() => setIsLiveEnabled(!isLiveEnabled)}
                  />
                  <div className={`block w-10 h-6 rounded-full transition-colors ${isLiveEnabled ? 'bg-green-500 shadow-inner' : 'bg-gray-300'}`}></div>
                  <div className={`absolute left-1 top-1 bg-white w-4 h-4 rounded-full shadow transition-transform ${isLiveEnabled ? 'translate-x-4' : 'translate-x-0'}`}></div>
                </div>
                <div className="ml-3">
                  <span className="text-sm font-bold text-gray-700 block">Live Monitoring</span>
                  <span className="text-[10px] text-gray-500">Auto-update on traffic events</span>
                </div>
              </label>
              {lastCalculated && (
                <div className="text-right">
                  <span className="text-[10px] text-gray-400 block italic">Synched at</span>
                  <span className="text-[10px] font-bold text-primary-600 font-mono tracking-tight">{lastCalculated}</span>
                </div>
              )}
            </div>
          </form>

          {error && (
            <div className="p-4 bg-red-50 text-red-700 rounded-lg border border-red-100 text-sm">
              {error}
            </div>
          )}

          {result && (
            <div className="space-y-6 animate-in slide-in-from-left duration-300">


              <div className="grid grid-cols-2 gap-3">
                <div className={`p-3 bg-gray-50 rounded-lg border border-gray-200 text-center transition-all duration-500 ${distanceChanged ? 'ring-2 ring-green-500 bg-green-50 scale-105' : ''
                  }`}>
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Distance</p>
                  <p className={`text-lg font-bold text-gray-900 transition-all ${distanceChanged ? 'text-green-600 animate-pulse' : ''
                    }`}>
                    {result.distance_km} km
                  </p>
                  {distanceChanged && previousResult && (
                    <p className="text-xs text-green-600 font-semibold mt-1">
                      {previousResult.distance_km > result.distance_km ? '↓' : '↑'}
                      {Math.abs(result.distance_km - previousResult.distance_km).toFixed(1)} km
                    </p>
                  )}
                </div>
                <div className={`p-3 bg-gray-50 rounded-lg border border-gray-200 text-center transition-all duration-500 ${etaChanged ? 'ring-2 ring-green-500 bg-green-50 scale-105' : ''
                  }`}>
                  <p className="text-xs text-gray-500 uppercase tracking-wide">Duration</p>
                  <p className={`text-lg font-bold text-gray-900 transition-all ${etaChanged ? 'text-green-600 animate-pulse' : ''
                    }`}>
                    {result.duration_minutes} min
                  </p>
                  {etaChanged && previousResult && (
                    <p className="text-xs text-green-600 font-semibold mt-1">
                      {previousResult.duration_minutes > result.duration_minutes ? '↓' : '↑'}
                      {Math.abs(result.duration_minutes - previousResult.duration_minutes)} min
                    </p>
                  )}
                </div>
                <div className="col-span-2 p-3 bg-gradient-to-r from-green-50 to-emerald-50 rounded-lg border border-green-100 flex items-center justify-between shadow-sm">
                  <div className="flex items-center gap-2">
                    <div className="bg-green-100 p-1.5 rounded-full">
                      <Leaf className="w-5 h-5 text-green-600" />
                    </div>
                    <div>
                      <span className="text-xs text-green-700 font-semibold uppercase tracking-wider block">Eco-Impact</span>
                      <span className="text-sm text-green-800">CO₂ savings estimated</span>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-xl font-black text-green-900">{result.estimated_co2_kg}</span>
                    <span className="text-xs font-bold text-green-700 ml-1">kg</span>
                  </div>
                </div>
              </div>



              {/* Turn-by-Turn Directions */}
              {result.steps && result.steps.length > 0 && (
                <div className="border-t border-gray-100 pt-6">
                  <h4 className="font-bold text-gray-900 mb-4 text-base flex items-center gap-2">
                    <Navigation className="w-5 h-5 text-primary-600" />
                    Route Instructions
                  </h4>
                  <div className="space-y-0" key={lastCalculated}>
                    {result.steps.map((step, i) => (
                      <div
                        key={`${lastCalculated}-${i}`}
                        className={`group flex gap-4 text-sm relative cursor-pointer transition-all ${activeStepIndex === i ? 'scale-[1.02]' : ''}`}
                        onClick={() => {
                          setActiveStepIndex(i);
                          if (window.innerWidth < 768) setIsSidebarOpen(false);
                        }}
                      >
                        <div className="flex flex-col items-center">
                          <div className={`w-3 h-3 rounded-full ${i === 0 ? 'bg-green-500' : i === result.steps.length - 1 ? 'bg-red-500' : 'bg-primary-400'} border-2 border-white shadow-sm z-10`} />
                          {i !== result.steps.length - 1 && <div className="w-0.5 h-full bg-gray-200 group-hover:bg-primary-200 transition-colors" />}
                        </div>
                        <div className="flex-1 pb-6">
                          <div className={`p-3 rounded-xl border shadow-sm transition-all ${activeStepIndex === i
                            ? 'bg-primary-50 border-primary-400 shadow-md ring-1 ring-primary-400'
                            : 'bg-white border-gray-100 group-hover:border-primary-200 group-hover:shadow-md'
                            }`}>
                            <p
                              className="text-gray-800 font-medium leading-relaxed"
                              dangerouslySetInnerHTML={{ __html: step.maneuver?.instruction || step.instruction || 'Continue' }}
                            />
                            {(step.distance > 0 || step.duration > 0) && (
                              <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                                {step.distance > 0 && (
                                  <span className="flex items-center gap-1 bg-gray-50 px-2 py-0.5 rounded border border-gray-100">
                                    <Navigation className="w-3 h-3 rotate-45" />
                                    {(step.distance / 1000).toFixed(2)} km
                                  </span>
                                )}
                                {step.duration > 0 && (
                                  <span className="flex items-center gap-1 bg-gray-50 px-2 py-0.5 rounded border border-gray-100">
                                    <Clock className="w-3 h-3" />
                                    {Math.round(step.duration / 60)} min
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Main Map Area */}
      <div className="flex-1 relative h-full bg-gray-200">
        <div className="absolute top-4 right-4 z-[400] flex flex-col gap-2">
          {result && (
            <button
              onClick={() => {
                setActiveStepIndex(null);
                // Trigger map bounds reset via a trick or prop if needed, 
                // but MapComponent already handles it on result change.
                // We'll rely on the 'Recenter' logic in MapComponent.
              }}
              className="bg-white p-3 rounded-xl shadow-lg hover:bg-gray-50 text-primary-600 transition-all border border-gray-100 group"
              title="Reset Route View"
            >
              <Navigation className="w-6 h-6 group-hover:scale-110 transition-transform" />
            </button>
          )}
        </div>

        <MapComponent
          startPoint={result?.start_point}
          endPoint={result?.end_point}
          geometry={result?.geometry}
          detailedGeometry={result?.detailed_geometry}
          steps={result?.steps}
          activeStepIndex={activeStepIndex}
          onStepClick={(i) => setActiveStepIndex(i)}
          simulatedEvent={simulatedEvent}
          isCalculating={loading}
        />

        {showNotification && (
          <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-[500] bg-gradient-to-r from-green-600 to-emerald-600 text-white px-6 py-4 rounded-2xl shadow-2xl flex items-center gap-4 animate-in slide-in-from-top duration-500">
            <div className="bg-white/20 p-2 rounded-full animate-pulse">
              <span className="text-2xl">🔄</span>
            </div>
            <div className="flex-1">
              <p className="font-bold text-base">Route Updated!</p>
              <p className="text-sm opacity-90">
                Rerouted to avoid {simulatedEvent?.event_name}
              </p>
              {previousResult && result && (
                <div className="flex gap-3 mt-1 text-xs">
                  {previousResult.duration_minutes !== result.duration_minutes && (
                    <span className="bg-white/20 px-2 py-0.5 rounded">
                      {previousResult.duration_minutes > result.duration_minutes ? '⚡ Faster' : '⏱️ Slower'} by {Math.abs(result.duration_minutes - previousResult.duration_minutes)} min
                    </span>
                  )}
                  {previousResult.distance_km !== result.distance_km && (
                    <span className="bg-white/20 px-2 py-0.5 rounded">
                      {previousResult.distance_km > result.distance_km ? '📍 Shorter' : '📍 Longer'} by {Math.abs(result.distance_km - previousResult.distance_km).toFixed(1)} km
                    </span>
                  )}
                </div>
              )}
            </div>
            <button
              onClick={() => setShowNotification(false)}
              className="ml-2 hover:bg-white/20 p-1.5 rounded-full transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        )}

        {!result && !loading && (
          <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-[400] bg-white/90 backdrop-blur-sm p-6 rounded-xl shadow-2xl text-center max-w-sm pointer-events-none">
            <div className="bg-primary-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4">
              <Navigation className="w-8 h-8 text-primary-600" />
            </div>
            <h2 className="text-xl font-bold text-gray-800 mb-2">Ready to Navigate?</h2>
            <p className="text-gray-600 text-sm">Enter your origin and destination in the sidebar to visualize real-time efficient routes.</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default Routing
