
import React from "react";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";
import { Timer, Zap } from "lucide-react";

interface AutoControlSwitchProps {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  disabled?: boolean;
  className?: string;
}

const AutoControlSwitch = ({ 
  enabled, 
  onChange, 
  disabled = false,
  className 
}: AutoControlSwitchProps) => {
  return (
    <div className={cn("flex flex-col gap-2 p-4 rounded-xl glass", className)}>
      <div className="text-xs uppercase tracking-wider font-medium text-muted-foreground">
        Automatic Signal Control
      </div>
      
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {enabled ? (
            <Zap className="h-5 w-5 text-primary animate-pulse" />
          ) : (
            <Timer className="h-5 w-5 text-muted-foreground" />
          )}
          <span className={cn("font-medium", enabled ? "text-primary" : "text-muted-foreground")}>
            {enabled ? "Enabled" : "Disabled"}
          </span>
        </div>
        
        <Switch
          checked={enabled}
          onCheckedChange={onChange}
          disabled={disabled}
          className={cn(
            enabled && "bg-primary"
          )}
        />
      </div>
      
      <div className="text-xs text-muted-foreground mt-1">
        {enabled 
          ? "Smart traffic control system is actively managing signals based on traffic flow and timing rules."
          : "Enable to let the system automatically control traffic signals based on vehicle count and timing."}
      </div>
    </div>
  );
};

export default AutoControlSwitch;
