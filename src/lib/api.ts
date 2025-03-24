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
  type: "red_light" | "speeding" | "no_helmet" | "excess_passengers" | "other";
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
    console.log('Attempting to connect to traffic backend at:', `${API_BASE_URL}/api/traffic`);
    const response = await fetch(`${API_BASE_URL}/api/traffic`);
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const data = await response.json();
    console.log('Successfully received traffic data:', data);
    return data;
  } catch (error) {
    console.error("Error fetching traffic data:", error);
    toast.error("Failed to connect to traffic management system. Please ensure the Python backend is running on port 5000.");
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
    console.log(`Attempting to ${enabled ? 'enable' : 'disable'} auto control for ${intersectionId}`);
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
      throw new Error(result.error || "Failed to update auto control mode");
    }
  } catch (error) {
    console.error("Error toggling auto control mode:", error);
    toast.error("Could not toggle auto control. Is the backend server running?");
    return false;
  }
};

// Get camera URL with appropriate parameters
export const getCameraStreamUrl = (intersectionId: string, fps: number = 1): string => {
  return `${API_BASE_URL}/api/video_feed/${intersectionId}?fps=${fps}`;
};

// Enhanced violation checking with better error handling
export const checkTrafficViolations = async (intersectionId: string): Promise<boolean> => {
  try {
    console.log(`Checking for violations at intersection ${intersectionId}`);
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
        toast.success(`Detected ${result.violations} violation(s)!`);
      } else {
        toast.info("No violations detected in the current frame.");
      }
      return result.violations > 0;
    } else {
      throw new Error(result.error || "Failed to check for violations");
    }
  } catch (error) {
    console.error("Error checking violations:", error);
    toast.error("Could not check for violations. Is the backend server running?");
    return false;
  }
};

// Enhanced violations fetch with better error handling
export const fetchViolations = async (): Promise<ViolationData[]> => {
  try {
    console.log('Fetching violations data');
    const response = await fetch(`${API_BASE_URL}/api/traffic/violations`);
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const data = await response.json();
    console.log('Successfully received violations data:', data);
    return Array.isArray(data) ? data : [];
  } catch (error) {
    console.error("Error fetching violations:", error);
    toast.error("Could not fetch violation data. Is the backend server running?");
    return [];
  }
};
