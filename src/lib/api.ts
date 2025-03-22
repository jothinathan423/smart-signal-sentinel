
// API interface for communicating with our Python backend
import { toast } from "sonner";

export interface TrafficData {
  intersectionId: string;
  vehicleCount: number;
  hasEmergencyVehicle: boolean;
  timestamp: string;
  status?: "red" | "yellow" | "green";
  autoMode?: boolean;
}

export interface ViolationData {
  id: string;
  vehicleNumber: string;
  type: "red_light" | "speeding" | "other";
  timestamp: string;
  location: string;
  details?: string;
  imageUrl?: string;
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

// Toggle automatic traffic control mode
export const toggleAutoMode = async (
  intersectionId: string,
  enabled: boolean
): Promise<boolean> => {
  try {
    console.log(`Setting auto control mode for ${intersectionId} to ${enabled ? 'enabled' : 'disabled'}`);
    const response = await fetch(`${API_BASE_URL}/api/traffic/auto_control`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intersectionId, enabled }),
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const result = await response.json();
    
    if (result.success) {
      toast.success(`Auto control mode ${enabled ? 'enabled' : 'disabled'}`);
      return true;
    } else {
      toast.error(result.error || "Failed to update auto control mode");
      return false;
    }
  } catch (error) {
    console.error("Error toggling auto control mode:", error);
    toast.error("Failed to toggle auto control. Check backend connection.");
    return false;
  }
};

// Get camera URL with appropriate parameters
export const getCameraStreamUrl = (fps: number = 1): string => {
  return `${API_BASE_URL}/api/video_feed?fps=${fps}`;
};

// Trigger traffic violation check on the backend
export const checkTrafficViolations = async (intersectionId: string): Promise<boolean> => {
  try {
    console.log(`Checking for traffic violations at intersection ${intersectionId}`);
    const response = await fetch(`${API_BASE_URL}/api/traffic/check_violations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intersectionId }),
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const result = await response.json();
    
    if (result.success) {
      if (result.violations > 0) {
        toast.success(`Detected ${result.violations} traffic violation(s)!`);
      } else {
        toast.info("No traffic violations detected.");
      }
      return result.violations > 0;
    } else {
      toast.error(result.error || "Failed to check for traffic violations");
      return false;
    }
  } catch (error) {
    console.error("Error checking traffic violations:", error);
    toast.error("Failed to check for violations. Check backend connection.");
    return false;
  }
};

// Fetch recent traffic violations
export const fetchViolations = async (): Promise<ViolationData[]> => {
  try {
    console.log('Fetching traffic violations from:', `${API_BASE_URL}/api/traffic/violations`);
    const response = await fetch(`${API_BASE_URL}/api/traffic/violations`);
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const data = await response.json();
    console.log('Received violation data:', data);
    return data;
  } catch (error) {
    console.error("Error fetching traffic violations:", error);
    toast.error("Failed to fetch violation data. Make sure the backend server is running.");
    return [];
  }
};
