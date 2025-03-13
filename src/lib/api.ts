
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
    console.log('Fetching traffic data from:', `${API_BASE_URL}/api/traffic`);
    const response = await fetch(`${API_BASE_URL}/api/traffic`);
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const data = await response.json();
    console.log('Received traffic data:', data);
    return data;
  } catch (error) {
    console.error("Error fetching traffic data:", error);
    toast.error("Failed to fetch traffic data. Make sure the backend server is running.");
    return [];
  }
};

// Update traffic signal on the backend
export const updateTrafficSignal = async (
  intersectionId: string,
  status: "red" | "yellow" | "green"
): Promise<void> => {
  try {
    console.log(`Updating traffic signal at ${intersectionId} to ${status}`);
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
    toast.error("Failed to update traffic signal. Check backend connection.");
  }
};
