
import { useState, useEffect } from "react";
import { fetchTrafficData, TrafficData } from "@/lib/api";

// Mock data for demonstration
const mockIntersections = [
  {
    id: "int-001",
    name: "Main St & 5th Ave",
    vehicleCount: 12,
    status: "red" as const,
    emergency: false,
    lastUpdated: new Date().toLocaleTimeString(),
  },
  {
    id: "int-002",
    name: "Broadway & 42nd St",
    vehicleCount: 8,
    status: "green" as const,
    emergency: false,
    lastUpdated: new Date().toLocaleTimeString(),
  },
  {
    id: "int-003",
    name: "Park Ave & 34th St",
    vehicleCount: 15,
    status: "yellow" as const,
    emergency: true,
    lastUpdated: new Date().toLocaleTimeString(),
  },
  {
    id: "int-004",
    name: "Lexington & 59th St",
    vehicleCount: 5,
    status: "green" as const,
    emergency: false,
    lastUpdated: new Date().toLocaleTimeString(),
  },
];

// Generate mock history data
const generateHistoryData = () => {
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
  const [intersections, setIntersections] = useState(mockIntersections);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [historyData, setHistoryData] = useState(generateHistoryData());

  // This simulates fetching data from the backend
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        // In a real app, this would call the API
        // const data = await fetchTrafficData();
        
        // For demo purposes, we'll use the mock data and add some randomness
        const updatedIntersections = mockIntersections.map(intersection => ({
          ...intersection,
          vehicleCount: Math.floor(Math.random() * 20) + 1,
          emergency: Math.random() < 0.1, // 10% chance of emergency
          lastUpdated: new Date().toLocaleTimeString(),
        }));
        
        setIntersections(updatedIntersections);
        
        // Update history with a new data point
        setHistoryData(prev => {
          const newPoint = {
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            count: updatedIntersections.reduce((sum, int) => sum + int.vehicleCount, 0),
          };
          const updated = [...prev.slice(1), newPoint];
          return updated;
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
    
    // Refresh data every 5 seconds
    const interval = setInterval(fetchData, 5000);
    
    return () => clearInterval(interval);
  }, []);

  const updateTrafficStatus = (id: string, status: "red" | "yellow" | "green") => {
    setIntersections(prev => 
      prev.map(intersection => 
        intersection.id === id 
          ? { ...intersection, status, lastUpdated: new Date().toLocaleTimeString() } 
          : intersection
      )
    );
  };

  return {
    intersections,
    historyData,
    loading,
    error,
    updateTrafficStatus,
  };
};
