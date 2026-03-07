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
  speed?: number;
}

export interface TrafficPatternData {
  [intersectionId: string]: {
    patterns: Record<string, { avg_count: number; samples: number; peak_detected: boolean }>;
    predictions: {
      next_hour_prediction: number;
      trend: string;
      confidence: number;
      current_hour_avg: number;
      is_peak_hour: boolean;
    };
    current_hour: number;
  };
}

export interface SpeedData {
  [intersectionId: string]: {
    vehicles: { id: string; speed: number }[];
    average_speed: number;
    max_speed: number;
    speeding_count: number;
    speed_limit: number;
  };
}

export interface LearningLog {
  id: string;
  intersection_id: string;
  event_type: string;
  data: Record<string, any>;
  timestamp: string;
}

export interface CameraConfig {
  intersection_id: string;
  camera_source: string;
  camera_type: "usb" | "ip" | "rtsp";
  status: string;
}

// Base URL for the backend API
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000';

// Fetch traffic data from the backend
export const fetchTrafficData = async (): Promise<TrafficData[]> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/traffic`);
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error("Error fetching traffic data:", error);
    toast.error("Failed to connect to traffic management system.");
    return [];
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
    if (!response.ok) throw new Error(`API error: ${response.status}`);
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
    const response = await fetch(`${API_BASE_URL}/api/traffic/auto_control`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intersectionId, enabled }),
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    const result = await response.json();
    if (result.success) {
      toast.success(`Auto control mode ${enabled ? 'enabled' : 'disabled'}`);
      return true;
    }
    throw new Error(result.error || "Failed to update auto control mode");
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

// Check traffic violations
export const checkTrafficViolations = async (intersectionId: string): Promise<boolean> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/traffic/check_violations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intersectionId }),
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    const result = await response.json();
    if (result.success) {
      if (result.violations > 0) {
        toast.success(`Detected ${result.violations} violation(s)!`);
      } else {
        toast.info("No violations detected in the current frame.");
      }
      return result.violations > 0;
    }
    throw new Error(result.error || "Failed to check for violations");
  } catch (error) {
    console.error("Error checking violations:", error);
    toast.error("Could not check for violations. Is the backend server running?");
    return false;
  }
};

// Fetch violations
export const fetchViolations = async (): Promise<ViolationData[]> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/traffic/violations`);
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    const data = await response.json();
    return Array.isArray(data) ? data : [];
  } catch (error) {
    console.error("Error fetching violations:", error);
    toast.error("Could not fetch violation data.");
    return [];
  }
};

// Fetch traffic patterns and predictions
export const fetchTrafficPatterns = async (): Promise<TrafficPatternData | null> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/traffic/patterns`);
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error("Error fetching traffic patterns:", error);
    return null;
  }
};

// Fetch vehicle speed data
export const fetchSpeedData = async (): Promise<SpeedData | null> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/traffic/speeds`);
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error("Error fetching speed data:", error);
    return null;
  }
};

// Fetch learning logs
export const fetchLearningLogs = async (): Promise<LearningLog[]> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/traffic/learning_logs`);
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error("Error fetching learning logs:", error);
    return [];
  }
};

// Configure IP camera
export const configureCamera = async (
  intersectionId: string,
  cameraSource: string,
  cameraType: "usb" | "ip" | "rtsp"
): Promise<boolean> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/traffic/configure_camera`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intersectionId, cameraSource, cameraType }),
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    const result = await response.json();
    if (result.success) {
      toast.success(`Camera configured for ${intersectionId}`);
      return true;
    }
    toast.error(result.error || "Failed to configure camera");
    return false;
  } catch (error) {
    console.error("Error configuring camera:", error);
    toast.error("Could not configure camera. Is the backend running?");
    return false;
  }
};

// Fetch camera configurations
export const fetchCameraConfigs = async (): Promise<CameraConfig[]> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/traffic/cameras`);
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error("Error fetching camera configs:", error);
    return [];
  }
};

// Fetch congestion summary
export const fetchCongestionSummary = async (): Promise<Record<string, any> | null> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/traffic/congestion`);
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error("Error fetching congestion summary:", error);
    return null;
  }
};
