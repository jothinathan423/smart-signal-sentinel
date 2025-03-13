
// API interface for communicating with our Python backend
import { toast } from "sonner";

export interface TrafficData {
  intersectionId: string;
  vehicleCount: number;
  hasEmergencyVehicle: boolean;
  timestamp: string;
  status?: "red" | "yellow" | "green";
}

// Base URL for the backend API
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

// Fetch traffic data from the backend
export const fetchTrafficData = async (): Promise<TrafficData[]> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/traffic`);
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error("Error fetching traffic data:", error);
    toast.error("Failed to fetch traffic data");
    
    // Return mock data in case of error to prevent UI from breaking
    return generateMockData();
  }
};

// Update traffic signal on the backend
export const updateTrafficSignal = async (
  intersectionId: string,
  status: "red" | "yellow" | "green"
): Promise<void> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/traffic/signal`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intersectionId, status }),
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const result = await response.json();
    
    if (result.success) {
      toast.success(`Traffic signal updated to ${status}`);
    } else {
      toast.error(result.error || "Failed to update traffic signal");
    }
  } catch (error) {
    console.error("Error updating traffic signal:", error);
    toast.error("Failed to update traffic signal");
  }
};

// Generate mock data in case the backend is not available
const generateMockData = (): TrafficData[] => {
  return [
    {
      intersectionId: "int-001",
      vehicleCount: Math.floor(Math.random() * 20) + 1,
      hasEmergencyVehicle: Math.random() < 0.1,
      timestamp: new Date().toISOString(),
      status: "red",
    },
    {
      intersectionId: "int-002",
      vehicleCount: Math.floor(Math.random() * 20) + 1,
      hasEmergencyVehicle: Math.random() < 0.1,
      timestamp: new Date().toISOString(),
      status: "green",
    },
    {
      intersectionId: "int-003",
      vehicleCount: Math.floor(Math.random() * 20) + 1,
      hasEmergencyVehicle: Math.random() < 0.1,
      timestamp: new Date().toISOString(),
      status: "yellow",
    },
    {
      intersectionId: "int-004",
      vehicleCount: Math.floor(Math.random() * 20) + 1,
      hasEmergencyVehicle: Math.random() < 0.1,
      timestamp: new Date().toISOString(),
      status: "green",
    },
  ];
};
