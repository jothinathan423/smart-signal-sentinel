
import React from "react";
import { cn } from "@/lib/utils";
import { AlertTriangle, Ambulance } from "lucide-react";

interface EmergencyAlertProps {
  active: boolean;
  className?: string;
}

const EmergencyAlert = ({ active, className }: EmergencyAlertProps) => {
  if (!active) return null;

  return (
    <div
      className={cn(
        "p-4 rounded-xl flex items-center gap-4 bg-traffic-emergency/10 border border-traffic-emergency/20 animate-emergency-pulse",
        className
      )}
    >
      <div className="bg-traffic-emergency text-white p-3 rounded-full">
        <Ambulance className="w-6 h-6" />
      </div>
      <div className="flex-1">
        <h3 className="font-medium text-traffic-emergency">Emergency Vehicle Detected</h3>
        <p className="text-sm text-muted-foreground">Traffic signal priority activated</p>
      </div>
      <AlertTriangle className="w-6 h-6 text-traffic-emergency animate-pulse" />
    </div>
  );
};

export default EmergencyAlert;
