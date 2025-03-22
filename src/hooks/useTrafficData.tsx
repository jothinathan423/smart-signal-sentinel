import { useState, useEffect, useCallback } from "react";
import { 
  fetchTrafficData, 
  updateTrafficSignal, 
  getCameraStreamUrl, 
  TrafficData,
  checkTrafficViolations,
  fetchViolations,
  ViolationData
} from "@/lib/api";

// Define the intersection data structure
export interface Intersection {
  id: string;
  name: string;
  vehicleCount: number;
  status: "red" | "yellow" | "green";
  emergency: boolean;
  lastUpdated: string;
}

// Define the history data point structure
export interface HistoryDataPoint {
  time: string;
  count: number;
}

// Single intersection name
const intersectionName = "Main Street Intersection";

// Generate initial history data
const generateHistoryData = (): HistoryDataPoint[] => {
  const data = [];
  const now = new Date();
  
  for (let i = 60; i >= 0; i--) {
    const time = new Date(now);
    time.setMinutes(now.getMinutes() - i);
    
    data.push({
      time: time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      count: Math.floor(Math.random() * 20) + 5,
    });
  }
  
  return data;
};

export const useTrafficData = () => {
  const [intersections, setIntersections] = useState<Intersection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [historyData, setHistoryData] = useState<HistoryDataPoint[]>(generateHistoryData());
  const [cameraUrl, setCameraUrl] = useState<string>("");
  const [violations, setViolations] = useState<ViolationData[]>([]);
  const [loadingViolations, setLoadingViolations] = useState(false);
  
  // Optimize camera URL with a timestamp-based approach
  useEffect(() => {
    // Use the optimized camera URL function
    setCameraUrl(getCameraStreamUrl());
  }, []);

  // Fetch traffic data from the backend
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const data = await fetchTrafficData();
        
        // Map API data to intersection objects - expect only one result
        const updatedIntersections = data.map(item => ({
          id: item.intersectionId,
          name: intersectionName,
          vehicleCount: item.vehicleCount,
          status: item.status || "red",
          emergency: item.hasEmergencyVehicle,
          lastUpdated: item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : 'N/A',
        }));
        
        setIntersections(updatedIntersections);
        
        // Update history with a new data point
        setHistoryData(prev => {
          const newPoint = {
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            count: updatedIntersections.reduce((sum, int) => sum + int.vehicleCount, 0),
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

  // Check for traffic violations
  const checkViolations = useCallback(async () => {
    if (intersections.length === 0) return false;
    
    const result = await checkTrafficViolations(intersections[0].id);
    
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
    cameraUrl,
    violations,
    loadingViolations,
    checkViolations,
    refreshViolations: loadViolations,
  };
};
