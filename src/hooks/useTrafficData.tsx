
import { useState, useEffect, useCallback } from "react";
import { 
  fetchTrafficData, 
  updateTrafficSignal, 
  getCameraStreamUrl, 
  TrafficData,
  checkTrafficViolations,
  fetchViolations,
  ViolationData,
  toggleAutoMode
} from "@/lib/api";

// Define the intersection data structure
export interface Intersection {
  id: string;
  name: string;
  vehicleCount: number;
  status: "red" | "yellow" | "green";
  emergency: boolean;
  lastUpdated: string;
  autoMode?: boolean;
}

// Define the history data point structure
export interface HistoryDataPoint {
  time: string;
  int1Count: number;
  int2Count: number;
}

// Intersection names
const intersectionNames = {
  "int-001": "Main Street Intersection",
  "int-002": "Park Avenue Intersection"
};

// Generate initial history data
const generateHistoryData = (): HistoryDataPoint[] => {
  const data = [];
  const now = new Date();
  
  for (let i = 60; i >= 0; i--) {
    const time = new Date(now);
    time.setMinutes(now.getMinutes() - i);
    
    data.push({
      time: time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      int1Count: Math.floor(Math.random() * 20) + 5,
      int2Count: Math.floor(Math.random() * 20) + 5,
    });
  }
  
  return data;
};

export const useTrafficData = () => {
  const [intersections, setIntersections] = useState<Intersection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [historyData, setHistoryData] = useState<HistoryDataPoint[]>(generateHistoryData());
  const [cameraUrls, setCameraUrls] = useState<Record<string, string>>({});
  const [violations, setViolations] = useState<ViolationData[]>([]);
  const [loadingViolations, setLoadingViolations] = useState(false);
  
  // Optimize camera URL with a timestamp-based approach
  useEffect(() => {
    // Use the optimized camera URL function for each intersection
    setCameraUrls({
      "int-001": getCameraStreamUrl("int-001"),
      "int-002": getCameraStreamUrl("int-002")
    });
  }, []);

  // Fetch traffic data from the backend
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const data = await fetchTrafficData();
        
        // Map API data to intersection objects
        const updatedIntersections = data.map(item => ({
          id: item.intersectionId,
          name: intersectionNames[item.intersectionId as keyof typeof intersectionNames] || "Unknown Intersection",
          vehicleCount: item.vehicleCount,
          status: item.status || "red",
          emergency: item.hasEmergencyVehicle,
          lastUpdated: item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : 'N/A',
          autoMode: item.autoMode || false,
        }));
        
        setIntersections(updatedIntersections);
        
        // Update history with new data points
        setHistoryData(prev => {
          const int1 = updatedIntersections.find(i => i.id === "int-001");
          const int2 = updatedIntersections.find(i => i.id === "int-002");
          
          const newPoint = {
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            int1Count: int1 ? int1.vehicleCount : 0,
            int2Count: int2 ? int2.vehicleCount : 0,
          };
          
          return [...prev.slice(1), newPoint];
        });
        
        setError(null);
      } catch (err) {
        console.error("Failed to fetch traffic data:", err);
        setError("Failed to fetch traffic data. Please ensure the backend server is running.");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    
    // Refresh data every 3 seconds
    const interval = setInterval(fetchData, 3000);
    
    return () => clearInterval(interval);
  }, []);

  // Update traffic signal status
  const updateTrafficStatus = useCallback(async (id: string, status: "red" | "yellow" | "green") => {
    try {
      await updateTrafficSignal(id, status);
      
      // Optimistically update the UI
      setIntersections(prev => 
        prev.map(intersection => 
          intersection.id === id 
            ? { ...intersection, status, lastUpdated: new Date().toLocaleTimeString() } 
            : intersection
        )
      );
    } catch (err) {
      console.error("Failed to update traffic signal:", err);
    }
  }, []);

  // Toggle automatic traffic signal control
  const toggleAutoTrafficControl = useCallback(async (id: string, enabled: boolean) => {
    try {
      const success = await toggleAutoMode(id, enabled);
      
      if (success) {
        // Optimistically update the UI
        setIntersections(prev => 
          prev.map(intersection => 
            intersection.id === id 
              ? { ...intersection, autoMode: enabled, lastUpdated: new Date().toLocaleTimeString() } 
              : intersection
          )
        );
      }
      
      return success;
    } catch (err) {
      console.error("Failed to toggle auto traffic control:", err);
      return false;
    }
  }, []);

  // Check for traffic violations
  const checkViolations = useCallback(async (intersectionId: string) => {
    if (!intersectionId && intersections.length === 0) return false;
    
    // If no intersection specified, check the first one
    const idToCheck = intersectionId || intersections[0].id;
    
    const result = await checkTrafficViolations(idToCheck);
    
    // Refresh violations list if violations were found
    if (result) {
      await loadViolations();
    }
    
    return result;
  }, [intersections]);

  // Load traffic violations
  const loadViolations = useCallback(async () => {
    try {
      setLoadingViolations(true);
      const data = await fetchViolations();
      setViolations(data);
    } catch (err) {
      console.error("Failed to fetch violations:", err);
    } finally {
      setLoadingViolations(false);
    }
  }, []);

  // Load violations when component mounts
  useEffect(() => {
    loadViolations();
  }, [loadViolations]);

  return {
    intersections,
    historyData,
    loading,
    error,
    updateTrafficStatus,
    cameraUrls,
    violations,
    loadingViolations,
    checkViolations,
    refreshViolations: loadViolations,
    toggleAutoTrafficControl,
  };
};
