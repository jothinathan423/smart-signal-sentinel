
import React from "react";
import { cn } from "@/lib/utils";
import TrafficLight from "./TrafficLight";
import VehicleCounter from "./VehicleCounter";
import EmergencyAlert from "./EmergencyAlert";
import AutoControlSwitch from "./AutoControlSwitch";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface IntersectionProps {
  id: string;
  name: string;
  vehicleCount: number;
  status: "red" | "yellow" | "green";
  emergency: boolean;
  lastUpdated: string;
  autoMode?: boolean;
  className?: string;
  onStatusChange?: (id: string, status: "red" | "yellow" | "green") => void;
  onAutoModeChange?: (id: string, enabled: boolean) => void;
}

const Intersection = ({
  id,
  name,
  vehicleCount,
  status,
  emergency,
  lastUpdated,
  autoMode = false,
  className,
  onStatusChange,
  onAutoModeChange,
}: IntersectionProps) => {
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
        <CardTitle className="text-lg">{name}</CardTitle>
        <div className="text-xs text-muted-foreground">Last updated: {lastUpdated}</div>
      </CardHeader>
      <CardContent className="pb-2">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <TrafficLight status={status} emergency={emergency} />
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
            disabled={autoMode}
          >
            Red
          </Button>
          <Button
            variant="outline"
            size="sm"
            className={cn(status === "yellow" && "bg-traffic-yellow/10 border-traffic-yellow/20 text-black")}
            onClick={() => handleStatusChange("yellow")}
            disabled={autoMode}
          >
            Yellow
          </Button>
          <Button
            variant="outline"
            size="sm"
            className={cn(status === "green" && "bg-traffic-green/10 border-traffic-green/20 text-traffic-green")}
            onClick={() => handleStatusChange("green")}
            disabled={autoMode}
          >
            Green
          </Button>
        </div>
      </CardFooter>
    </Card>
  );
};

export default Intersection;
