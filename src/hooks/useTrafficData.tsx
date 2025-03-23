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
import { toast } from "sonner";

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
  [key: string]: string | number;
}

// Intersection names
const intersectionNames = {
  "int-001": "Main Street",
  "int-002": "Park Avenue"
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
      "Main Street": Math.floor(Math.random() * 20) + 5,
      "Park Avenue": Math.floor(Math.random() * 20) + 5,
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
    const updateCameraUrls = () => {
      setCameraUrls({
        "int-001": `${getCameraStreamUrl("int-001")}?t=${Date.now()}`,
        "int-002": `${getCameraStreamUrl("int-002")}?t=${Date.now()}`
      });
    };
    
    updateCameraUrls();
    
    // Update camera URLs every 10 seconds to avoid caching
    const cameraInterval = setInterval(updateCameraUrls, 10000);
    
    return () => clearInterval(cameraInterval);
  }, []);

  // Fetch traffic data from the backend
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const data = await fetchTrafficData();
        
        if (!data || data.length === 0) {
          console.error("No data received from traffic API");
          return;
        }
        
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
          const newPoint: HistoryDataPoint = {
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          };
          
          // Add data for each intersection
          updatedIntersections.forEach(intersection => {
            const intersectionName = intersectionNames[intersection.id as keyof typeof intersectionNames];
            if (intersectionName) {
              newPoint[intersectionName] = intersection.vehicleCount;
            }
          });
          
          // Keep only the last 60 data points
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
      toast.error("Failed to update traffic signal. Check connection.");
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
        
        toast.success(`Auto control ${enabled ? 'enabled' : 'disabled'} for ${intersectionNames[id as keyof typeof intersectionNames]}`);
      }
      
      return success;
    } catch (err) {
      console.error("Failed to toggle auto traffic control:", err);
      toast.error("Failed to toggle auto mode. Check connection.");
      return false;
    }
  }, []);

  // Check for traffic violations
  const checkViolations = useCallback(async (intersectionId: string) => {
    try {
      if (!intersectionId) {
        toast.error("Invalid intersection ID");
        return false;
      }
      
      toast.info("Checking for traffic violations...");
      const result = await checkTrafficViolations(intersectionId);
      
      // Refresh violations list regardless of result
      await loadViolations();
      
      return result;
    } catch (err) {
      console.error("Error checking violations:", err);
      toast.error("Failed to check violations. Check connection.");
      return false;
    }
  }, []);

  // Load traffic violations
  const loadViolations = useCallback(async () => {
    try {
      setLoadingViolations(true);
      const data = await fetchViolations();
      setViolations(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Failed to fetch violations:", err);
      toast.error("Failed to load violations data");
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
