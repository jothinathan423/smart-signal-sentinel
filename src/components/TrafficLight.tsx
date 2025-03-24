
import React, { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

type TrafficLightStatus = "red" | "yellow" | "green";

interface TrafficLightProps {
  status: TrafficLightStatus;
  emergency: boolean;
  className?: string;
}

const TrafficLight = ({ status, emergency, className }: TrafficLightProps) => {
  const [prevStatus, setPrevStatus] = useState<TrafficLightStatus>(status);
  const [isTransitioning, setIsTransitioning] = useState(false);

  useEffect(() => {
    if (status !== prevStatus) {
      setIsTransitioning(true);
      const timer = setTimeout(() => {
        setIsTransitioning(false);
        setPrevStatus(status);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [status, prevStatus]);

  // Debug log to check if emergency state is being properly passed
  console.log(`TrafficLight: status=${status}, emergency=${emergency}`);

  return (
    <div className={cn("flex flex-col gap-4 p-4 rounded-xl glass", className)}>
      <div className="text-xs uppercase tracking-wider font-medium text-muted-foreground">
        Traffic Signal
      </div>
      <div className="flex flex-col gap-3 items-center">
        <div
          className={cn(
            "w-16 h-16 rounded-full flex items-center justify-center transition-all duration-300 border",
            status === "red" ? "bg-traffic-red text-white border-traffic-red/20" : "bg-traffic-red/20 text-traffic-red/40",
            status === "red" && "traffic-light-glow",
            isTransitioning && status === "red" && "animate-pulse-red",
            emergency && status !== "green" && "animate-emergency-pulse"
          )}
          style={{ "--color": "rgba(255, 59, 48, 0.7)" } as React.CSSProperties}
        >
          <span className={cn("text-lg font-semibold", status !== "red" && "opacity-0")}>STOP</span>
        </div>
        <div
          className={cn(
            "w-16 h-16 rounded-full flex items-center justify-center transition-all duration-300 border",
            status === "yellow" ? "bg-traffic-yellow text-black border-traffic-yellow/20" : "bg-traffic-yellow/20 text-traffic-yellow/40",
            status === "yellow" && "traffic-light-glow",
            isTransitioning && status === "yellow" && "animate-pulse-red"
          )}
          style={{ "--color": "rgba(255, 204, 0, 0.7)" } as React.CSSProperties}
        >
          <span className={cn("text-sm font-semibold", status !== "yellow" && "opacity-0")}>WAIT</span>
        </div>
        <div
          className={cn(
            "w-16 h-16 rounded-full flex items-center justify-center transition-all duration-300 border",
            status === "green" ? "bg-traffic-green text-white border-traffic-green/20" : "bg-traffic-green/20 text-traffic-green/40",
            status === "green" && "traffic-light-glow",
            isTransitioning && status === "green" && "animate-pulse-red",
            emergency && status === "green" && "animate-emergency-pulse"
          )}
          style={{ "--color": "rgba(52, 199, 89, 0.7)" } as React.CSSProperties}
        >
          <span className={cn("text-sm font-semibold", status !== "green" && "opacity-0")}>GO</span>
        </div>
      </div>
    </div>
  );
};

export default TrafficLight;
