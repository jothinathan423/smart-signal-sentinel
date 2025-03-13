
import { useState, useEffect } from "react";
import { fetchTrafficData, updateTrafficSignal, TrafficData } from "@/lib/api";

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

// Mapping of intersection IDs to names
const intersectionNames: Record<string, string> = {
  "int-001": "Main St & 5th Ave",
  "int-002": "Broadway & 42nd St",
  "int-003": "Park Ave & 34th St",
  "int-004": "Lexington & 59th St",
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

  // Fetch traffic data from the backend
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const data = await fetchTrafficData();
        
        // Map API data to intersection objects
        const updatedIntersections = data.map(item => ({
          id: item.intersectionId,
          name: intersectionNames[item.intersectionId] || `Intersection ${item.intersectionId}`,
          vehicleCount: item.vehicleCount,
          status: item.status || "red",
          emergency: item.hasEmergencyVehicle,
          lastUpdated: new Date(item.timestamp).toLocaleTimeString(),
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
        setError("Failed to fetch traffic data. Please try again.");
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
  const updateTrafficStatus = async (id: string, status: "red" | "yellow" | "green") => {
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
  };

  return {
    intersections,
    historyData,
    loading,
    error,
    updateTrafficStatus,
  };
};
