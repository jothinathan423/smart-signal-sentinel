
import React from "react";
import { cn } from "@/lib/utils";
import TrafficLight from "./TrafficLight";
import VehicleCounter from "./VehicleCounter";
import EmergencyAlert from "./EmergencyAlert";
import AutoControlSwitch from "./AutoControlSwitch";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
    <div className={cn("space-y-4 animate-fade-in", className)}>
      {/* Main info card */}
      <Card className="overflow-hidden">
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
          <VehicleCounter count={vehicleCount} emergency={emergency} />
          <div className="my-4">
            <AutoControlSwitch
              enabled={autoMode}
              onChange={handleAutoModeChange}
            />
          </div>
          <EmergencyAlert active={emergency} />
        </CardContent>
        <CardFooter className="flex justify-between bg-muted/50 p-4">
          <div className="text-xs text-muted-foreground">ID: {id}</div>
          <div className="flex gap-2">
            {(["red", "yellow", "green"] as const).map(sig => (
              <Button
                key={sig}
                variant="outline"
                size="sm"
                className={cn(
                  status === sig && (
                    sig === "red" ? "bg-traffic-red/10 border-traffic-red/20 text-traffic-red" :
                    sig === "yellow" ? "bg-traffic-yellow/10 border-traffic-yellow/20 text-black" :
                    "bg-traffic-green/10 border-traffic-green/20 text-traffic-green"
                  )
                )}
                onClick={() => handleStatusChange(sig)}
                disabled={autoMode || !isCameraActive}
              >
                {sig.charAt(0).toUpperCase() + sig.slice(1)}
              </Button>
            ))}
          </div>
        </CardFooter>
      </Card>

      {/* 4 separate direction signal cards */}
      {signals ? (
        <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
          {(["north", "south", "east", "west"] as const).map(dir => {
            const sig = signals[dir] || "red";
            return (
              <Card key={dir} className={`overflow-hidden border-2 transition-all duration-300 ${
                sig === "green" ? "border-traffic-green/40" :
                sig === "yellow" ? "border-traffic-yellow/40" :
                "border-traffic-red/40"
              }`}>
                <CardContent className="p-4 flex flex-col items-center gap-3">
                  <div className="text-sm uppercase font-semibold tracking-wider text-muted-foreground">
                    {dir}
                  </div>
                  <div className="flex flex-col items-center gap-2 p-3 rounded-xl bg-muted/40">
                    <div className={`w-10 h-10 rounded-full transition-all duration-300 ${
                      sig === "red" ? "bg-traffic-red shadow-[0_0_12px_rgba(255,59,48,0.6)]" : "bg-traffic-red/20"
                    }`} />
                    <div className={`w-10 h-10 rounded-full transition-all duration-300 ${
                      sig === "yellow" ? "bg-traffic-yellow shadow-[0_0_12px_rgba(255,204,0,0.6)]" : "bg-traffic-yellow/20"
                    }`} />
                    <div className={`w-10 h-10 rounded-full transition-all duration-300 ${
                      sig === "green" ? "bg-traffic-green shadow-[0_0_12px_rgba(52,199,89,0.6)]" : "bg-traffic-green/20"
                    }`} />
                  </div>
                  <Badge variant="outline" className={`text-xs font-bold ${
                    sig === "green" ? "bg-traffic-green/10 text-traffic-green border-traffic-green/30" :
                    sig === "yellow" ? "bg-traffic-yellow/10 text-yellow-800 border-traffic-yellow/30" :
                    "bg-traffic-red/10 text-traffic-red border-traffic-red/30"
                  }`}>
                    {sig === "red" ? "STOP" : sig === "yellow" ? "WAIT" : "GO"}
                  </Badge>
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : (
        <Card>
          <CardContent className="p-4">
            <TrafficLight status={status} emergency={emergency} />
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default Intersection;
