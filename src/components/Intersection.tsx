
import React from "react";
import { cn } from "@/lib/utils";
import TrafficLight from "./TrafficLight";
import VehicleCounter from "./VehicleCounter";
import EmergencyAlert from "./EmergencyAlert";
import AutoControlSwitch from "./AutoControlSwitch";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type { DirectionalSignals } from "@/hooks/useTrafficData";

interface IntersectionProps {
  id: string;
  name: string;
  vehicleCount: number;
  status: "red" | "yellow" | "green";
  signals?: DirectionalSignals;
  emergency: boolean;
  lastUpdated: string;
  autoMode?: boolean;
  cameraStatus?: string;
  className?: string;
  onStatusChange?: (id: string, status: "red" | "yellow" | "green") => void;
  onAutoModeChange?: (id: string, enabled: boolean) => void;
}

const Intersection = ({
  id,
  name,
  vehicleCount,
  status,
  signals,
  emergency,
  lastUpdated,
  autoMode = false,
  cameraStatus,
  className,
  onStatusChange,
  onAutoModeChange,
}: IntersectionProps) => {
  const isCameraActive = cameraStatus === "active";
  const handleStatusChange = (newStatus: "red" | "yellow" | "green") => {
    if (onStatusChange && !autoMode) {
      onStatusChange(id, newStatus);
    }
  };

  const handleAutoModeChange = (enabled: boolean) => {
    if (onAutoModeChange) {
      onAutoModeChange(id, enabled);
    }
  };

  return (
    <Card className={cn("overflow-hidden animate-fade-in", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">{name}</CardTitle>
          {cameraStatus && !isCameraActive && (
            <span className={cn(
              "text-xs px-2 py-0.5 rounded-full font-medium",
              cameraStatus === "failed" ? "bg-destructive/10 text-destructive" :
              cameraStatus === "reconnecting" ? "bg-yellow-100 text-yellow-800" :
              "bg-muted text-muted-foreground"
            )}>
              {cameraStatus === "failed" ? "Camera Failed" :
               cameraStatus === "reconnecting" ? "Reconnecting..." :
               cameraStatus === "configured" ? "Connecting..." : cameraStatus}
            </span>
          )}
        </div>
        <div className="text-xs text-muted-foreground">Last updated: {lastUpdated}</div>
      </CardHeader>
      <CardContent className="pb-2">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          {signals ? (
            <div className="flex flex-col gap-4 p-4 rounded-xl glass">
              <div className="text-xs uppercase tracking-wider font-medium text-muted-foreground">
                Traffic Signals
              </div>
              <div className="grid grid-cols-2 gap-3">
                {(["north", "south", "east", "west"] as const).map(dir => {
                  const sig = signals[dir] || "red";
                  return (
                    <div key={dir} className="flex flex-col items-center gap-1.5">
                      <span className="text-xs uppercase font-medium text-muted-foreground">{dir}</span>
                      <div className="flex gap-1.5">
                        <div className={cn("w-8 h-8 rounded-full border transition-all duration-300",
                          sig === "red" ? "bg-traffic-red border-traffic-red/20 traffic-light-glow" : "bg-traffic-red/20"
                        )} style={sig === "red" ? { "--color": "rgba(255, 59, 48, 0.7)" } as React.CSSProperties : {}} />
                        <div className={cn("w-8 h-8 rounded-full border transition-all duration-300",
                          sig === "yellow" ? "bg-traffic-yellow border-traffic-yellow/20 traffic-light-glow" : "bg-traffic-yellow/20"
                        )} style={sig === "yellow" ? { "--color": "rgba(255, 204, 0, 0.7)" } as React.CSSProperties : {}} />
                        <div className={cn("w-8 h-8 rounded-full border transition-all duration-300",
                          sig === "green" ? "bg-traffic-green border-traffic-green/20 traffic-light-glow" : "bg-traffic-green/20"
                        )} style={sig === "green" ? { "--color": "rgba(52, 199, 89, 0.7)" } as React.CSSProperties : {}} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <TrafficLight status={status} emergency={emergency} />
          )}
          <VehicleCounter count={vehicleCount} emergency={emergency} />
        </div>
        <div className="mb-4">
          <AutoControlSwitch 
            enabled={autoMode} 
            onChange={handleAutoModeChange} 
          />
        </div>
        <div>
          <EmergencyAlert active={emergency} />
        </div>
      </CardContent>
      <CardFooter className="flex justify-between bg-muted/50 p-4">
        <div className="text-xs text-muted-foreground">ID: {id}</div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            className={cn(status === "red" && "bg-traffic-red/10 border-traffic-red/20 text-traffic-red")}
            onClick={() => handleStatusChange("red")}
            disabled={autoMode || !isCameraActive}
          >
            Red
          </Button>
          <Button
            variant="outline"
            size="sm"
            className={cn(status === "yellow" && "bg-traffic-yellow/10 border-traffic-yellow/20 text-black")}
            onClick={() => handleStatusChange("yellow")}
            disabled={autoMode || !isCameraActive}
          >
            Yellow
          </Button>
          <Button
            variant="outline"
            size="sm"
            className={cn(status === "green" && "bg-traffic-green/10 border-traffic-green/20 text-traffic-green")}
            onClick={() => handleStatusChange("green")}
            disabled={autoMode || !isCameraActive}
          >
            Green
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
};

export default Intersection;
