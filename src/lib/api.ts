// API interface for communicating with the Python backend
import { toast } from "sonner";

export interface TrafficData {
  intersectionId: string;
  name: string;
  vehicleCount: number;
  pceDensity?: number;
  vehicleTypeCounts?: Record<string, number>;
  hasEmergencyVehicle: boolean;
  emergencyCount?: number;
  timestamp: string;
  status?: "red" | "yellow" | "green";
  autoMode?: boolean;
  cameraStatus?: string;
  zoneId?: string;
}

export interface SystemOverview {
  monitored_intersections: number;
  total_vehicles: number;
  total_pce_density: number;
  emergency_vehicles: number;
  emergency_intersections: number;
  active_cameras: number;
  auto_mode_count: number;
  total_zones: number;
  active_emergency_corridors: number;
  signal_controllers: number;
  yolo_model: string;
  cuda_available: boolean;
}

export interface SignalControllerStatus {
  [intersectionId: string]: {
    type: string;
    status: string;
    last_command: string | null;
    last_sent_at: string | null;
    failures: number;
    total_commands: number;
  };
}

export interface ZoneInfo {
  id: string;
  name: string;
  intersection_count: number;
  intersection_ids: string[];
  emergency_corridor_active: boolean;
  green_wave_enabled: boolean;
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
  name: string;
  camera_source: string;
  camera_type: "usb" | "ip" | "rtsp";
  status: string;
}

export interface IntersectionInfo {
  id: string;
  name: string;
  camera_source: string;
  camera_type: "usb" | "ip" | "rtsp";
  camera_status: string;
  signal: string;
  vehicle_count: number;
  auto_mode: boolean;
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

// Get MJPEG stream URL for a camera - this is a continuous stream, NOT a static image
export const getCameraStreamUrl = (intersectionId: string, fps: number = 15): string => {
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

// Configure camera for an existing intersection
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
      toast.success(result.message || `Camera configured for ${intersectionId}`);
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

// ============= NEW: Intersection management APIs =============

// Add a new intersection
export const addIntersection = async (
  intersectionId: string,
  name: string,
  cameraSource: string,
  cameraType: "usb" | "ip" | "rtsp"
): Promise<boolean> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/traffic/intersections`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intersectionId, name, cameraSource, cameraType }),
    });
    if (!response.ok) {
      const result = await response.json();
      toast.error(result.error || "Failed to add intersection");
      return false;
    }
    const result = await response.json();
    if (result.success) {
      toast.success(result.message || `Intersection ${name} added`);
      return true;
    }
    return false;
  } catch (error) {
    console.error("Error adding intersection:", error);
    toast.error("Could not add intersection. Is the backend running?");
    return false;
  }
};

// Remove an intersection
export const removeIntersection = async (intersectionId: string): Promise<boolean> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/traffic/intersections/${intersectionId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      const result = await response.json();
      toast.error(result.error || "Failed to remove intersection");
      return false;
    }
    const result = await response.json();
    if (result.success) {
      toast.success(result.message || `Intersection removed`);
      return true;
    }
    return false;
  } catch (error) {
    console.error("Error removing intersection:", error);
    toast.error("Could not remove intersection.");
    return false;
  }
};

// List all intersections
export const fetchIntersections = async (): Promise<IntersectionInfo[]> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/traffic/intersections`);
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error("Error fetching intersections:", error);
    return [];
  }
};

// ============= System Overview (City-Scale Dashboard) =============

export const fetchSystemOverview = async (): Promise<SystemOverview | null> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/stats/overview`);
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error("Error fetching system overview:", error);
    return null;
  }
};

// ============= Signal Controller APIs =============

export const fetchSignalControllers = async (): Promise<SignalControllerStatus> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/signal_controllers`);
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error("Error fetching signal controllers:", error);
    return {};
  }
};

export const configureSignalController = async (
  intersectionId: string,
  config: { type: string; endpoint?: string; authToken?: string; broker?: string; port?: number; topic?: string; pins?: Record<string, number> }
): Promise<boolean> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/signal_controllers/${intersectionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    const result = await response.json();
    if (result.success) {
      toast.success(result.message || 'Signal controller configured');
      return true;
    }
    return false;
  } catch (error) {
    console.error("Error configuring signal controller:", error);
    toast.error("Could not configure signal controller");
    return false;
  }
};

export const testSignalController = async (intersectionId: string, signal: string = 'green'): Promise<boolean> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/signal_controllers/${intersectionId}/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ signal }),
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    const result = await response.json();
    if (result.success) {
      toast.success('Test signal sent successfully');
      return true;
    }
    return false;
  } catch (error) {
    console.error("Error testing signal controller:", error);
    toast.error("Could not test signal controller");
    return false;
  }
};

// ============= Zone Management APIs =============

export const fetchZones = async (): Promise<ZoneInfo[]> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/zones`);
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error("Error fetching zones:", error);
    return [];
  }
};

export const createZone = async (zoneId: string, name: string, intersectionIds: string[]): Promise<boolean> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/zones`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ zoneId, name, intersectionIds }),
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    const result = await response.json();
    if (result.success) {
      toast.success(`Zone "${name}" created`);
      return true;
    }
    return false;
  } catch (error) {
    console.error("Error creating zone:", error);
    toast.error("Could not create zone");
    return false;
  }
};

export const activateEmergencyCorridor = async (zoneId: string, path: string[], vehicleId?: string): Promise<boolean> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/zones/${zoneId}/emergency_corridor`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, vehicleId }),
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    const result = await response.json();
    if (result.success) {
      toast.success('Emergency corridor activated');
      return true;
    }
    return false;
  } catch (error) {
    console.error("Error activating emergency corridor:", error);
    return false;
  }
};

// ============= SIMULATION APIs =============

export interface SimulationConfig {
  id: string;
  name: string;
  running: boolean;
  auto_spawn: boolean;
  spawn_rate: number;
  spawn_types: Record<string, number>;
  default_speed: number;
  speed_variance: number;
  signal: string;
  signals: Record<string, string>;
  vehicle_count: number;
  total_spawned: number;
  total_passed: number;
}

export const fetchSimulations = async (): Promise<SimulationConfig[]> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/simulation`);
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error("Error fetching simulations:", error);
    return [];
  }
};

export const createSimulation = async (
  intersectionId: string,
  config: Partial<SimulationConfig> & { name?: string }
): Promise<boolean> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/simulation/${intersectionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    const result = await response.json();
    if (result.success) {
      toast.success(`Simulation started for ${intersectionId}`);
      return true;
    }
    return false;
  } catch (error) {
    console.error("Error creating simulation:", error);
    toast.error("Could not create simulation.");
    return false;
  }
};

export const updateSimulation = async (
  intersectionId: string,
  config: Partial<SimulationConfig>
): Promise<boolean> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/simulation/${intersectionId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return true;
  } catch (error) {
    console.error("Error updating simulation:", error);
    return false;
  }
};

export const deleteSimulation = async (intersectionId: string): Promise<boolean> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/simulation/${intersectionId}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    toast.success("Simulation stopped");
    return true;
  } catch (error) {
    console.error("Error deleting simulation:", error);
    return false;
  }
};

export const spawnSimVehicle = async (
  intersectionId: string,
  options: { type?: string; direction?: string; speed?: number; lane?: number; is_violator?: boolean; helmet_violation?: boolean }
): Promise<string | null> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/simulation/${intersectionId}/spawn`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options),
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    const result = await response.json();
    return result.vehicleId || null;
  } catch (error) {
    console.error("Error spawning vehicle:", error);
    return null;
  }
};

export const clearSimVehicles = async (intersectionId: string): Promise<boolean> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/simulation/${intersectionId}/clear`, {
      method: 'POST',
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return true;
  } catch (error) {
    console.error("Error clearing vehicles:", error);
    return false;
  }
};

export const fetchSimulationStatus = async (intersectionId: string): Promise<any> => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/simulation/${intersectionId}/status`);
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return await response.json();
  } catch (error) {
    console.error("Error fetching simulation status:", error);
    return null;
  }
};
