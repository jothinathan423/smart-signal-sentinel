
import React from "react";
import { cn } from "@/lib/utils";
import { Car, Ambulance } from "lucide-react";

interface VehicleCounterProps {
  count: number;
  emergency: boolean;
  className?: string;
}

const VehicleCounter = ({ count, emergency, className }: VehicleCounterProps) => {
  return (
    <div className={cn("p-4 rounded-xl glass flex flex-col gap-2", className)}>
      <div className="text-xs uppercase tracking-wider font-medium text-muted-foreground">
        Vehicle Count
      </div>
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
          <Car className="w-6 h-6 text-primary" />
        </div>
        <div className="text-3xl font-semibold">{count}</div>
      </div>
      {emergency && (
        <div className="mt-2 flex items-center gap-2 p-2 rounded-lg bg-traffic-emergency/10 text-traffic-emergency animate-emergency-pulse">
          <Ambulance className="w-5 h-5" />
          <span className="text-sm font-medium">Emergency Vehicle Detected</span>
        </div>
      )}
    </div>
  );
};

export default VehicleCounter;
