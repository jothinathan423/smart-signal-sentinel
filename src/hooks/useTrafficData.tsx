import { useState, useEffect, useCallback } from "react";
import {
  fetchTrafficData,
  updateTrafficSignal,
  getCameraStreamUrl,
  TrafficData,
  checkTrafficViolations,
  fetchViolations,
  ViolationData,
  toggleAutoMode,
  fetchSystemOverview,
  SystemOverview,
} from "@/lib/api";
import { toast } from "sonner";

// Define the intersection data structure
export interface DirectionalSignals {
  north: "red" | "yellow" | "green";
  south: "red" | "yellow" | "green";
  east: "red" | "yellow" | "green";
  west: "red" | "yellow" | "green";
}

export interface Intersection {
  id: string;
  name: string;
  vehicleCount: number;
  status: "red" | "yellow" | "green";
  signals: DirectionalSignals;
  emergency: boolean;
  emergencyCount: number;
  lastUpdated: string;
  autoMode?: boolean;
  cameraStatus?: string;
  pceDensity?: number;
  zoneId?: string;
}

// Define the history data point structure
export interface HistoryDataPoint {
  time: string;
  [key: string]: string | number;
}

export const useTrafficData = () => {
  const [intersections, setIntersections] = useState<Intersection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [historyData, setHistoryData] = useState<HistoryDataPoint[]>([]);
  const [cameraUrls, setCameraUrls] = useState<Record<string, string>>({});
  const [violations, setViolations] = useState<ViolationData[]>([]);
  const [loadingViolations, setLoadingViolations] = useState(false);
  const [systemOverview, setSystemOverview] = useState<SystemOverview | null>(null);

  // Build camera URLs from intersection data - MJPEG streams are continuous,
  // so we only set the URL once per intersection (no timestamp cache-busting needed)
  const updateCameraUrls = useCallback((data: TrafficData[]) => {
    setCameraUrls(prev => {
      const newUrls: Record<string, string> = {};
      let changed = false;

      for (const item of data) {
        const url = getCameraStreamUrl(item.intersectionId, 15);
        newUrls[item.intersectionId] = url;
        if (prev[item.intersectionId] !== url) {
          changed = true;
        }
      }

      // Also check if intersections were removed
      if (Object.keys(prev).length !== Object.keys(newUrls).length) {
        changed = true;
      }

      return changed ? newUrls : prev;
    });
  }, []);

  // Fetch traffic data from the backend
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [data, overview] = await Promise.all([
          fetchTrafficData(),
          fetchSystemOverview(),
        ]);

        if (overview) {
          setSystemOverview(overview);
        }

        if (!data || data.length === 0) {
          if (!loading) return; // Don't show error on subsequent empty fetches
          return;
        }

        // Map API data to intersection objects - fully dynamic
        const updatedIntersections = data.map(item => {
          const status = item.status || "red" as const;
          const defaultSignals: DirectionalSignals = {
            north: status, south: status,
            east: status === "green" ? "red" : status === "red" ? "green" : "yellow",
            west: status === "green" ? "red" : status === "red" ? "green" : "yellow",
          };
          return {
            id: item.intersectionId,
            name: item.name || item.intersectionId,
            vehicleCount: item.vehicleCount,
            status,
            signals: (item as any).signals || defaultSignals,
            emergency: item.hasEmergencyVehicle,
            emergencyCount: item.emergencyCount || 0,
            lastUpdated: item.timestamp ? new Date(item.timestamp).toLocaleTimeString() : 'N/A',
            autoMode: item.autoMode || false,
            cameraStatus: item.cameraStatus,
            pceDensity: item.pceDensity || 0,
            zoneId: item.zoneId,
          };
        });

        setIntersections(updatedIntersections);
        updateCameraUrls(data);

        // Update history with new data points
        setHistoryData(prev => {
          const newPoint: HistoryDataPoint = {
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          };

          updatedIntersections.forEach(intersection => {
            newPoint[intersection.name] = intersection.vehicleCount;
          });

          const updated = [...prev, newPoint];
          // Keep last 60 data points
          return updated.length > 60 ? updated.slice(-60) : updated;
        });

        setError(null);
        setLoading(false);
      } catch (err) {
        console.error("Failed to fetch traffic data:", err);
        setError("Failed to fetch traffic data. Please ensure the backend server is running.");
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, [updateCameraUrls]);

  // Update traffic signal status
  const updateTrafficStatus = useCallback(async (id: string, status: "red" | "yellow" | "green") => {
    try {
      await updateTrafficSignal(id, status);
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
        setIntersections(prev =>
          prev.map(intersection =>
            intersection.id === id
              ? { ...intersection, autoMode: enabled, lastUpdated: new Date().toLocaleTimeString() }
              : intersection
          )
        );
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
    } finally {
      setLoadingViolations(false);
    }
  }, []);

  // Load violations on mount
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
    systemOverview,
  };
};
