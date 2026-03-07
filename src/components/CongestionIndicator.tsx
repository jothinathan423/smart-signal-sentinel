import React from "react";
import { cn } from "@/lib/utils";
import { AlertTriangle, TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface CongestionIndicatorProps {
  vehicleCount: number;
  trend?: string;
  confidence?: number;
  className?: string;
}

const CongestionIndicator = ({ vehicleCount, trend = "stable", confidence = 0, className }: CongestionIndicatorProps) => {
  const level = vehicleCount > 15 ? "High" : vehicleCount > 8 ? "Medium" : "Low";
  const percentage = Math.min(100, (vehicleCount / 25) * 100);

  const TrendIcon = trend === "increasing" ? TrendingUp : trend === "decreasing" ? TrendingDown : Minus;

  return (
    <div className={cn("p-4 rounded-xl glass flex flex-col gap-2", className)}>
      <div className="text-xs uppercase tracking-wider font-medium text-muted-foreground">
        Congestion Level
      </div>
      <div className="flex items-center justify-between">
        <Badge
          variant={level === "High" ? "destructive" : "outline"}
          className={cn(
            level === "Medium" && "bg-yellow-100 text-yellow-800 border-yellow-200",
            level === "Low" && "bg-green-100 text-green-800 border-green-200"
          )}
        >
          {level === "High" && <AlertTriangle className="h-3 w-3 mr-1" />}
          {level}
        </Badge>
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <TrendIcon className="h-3 w-3" />
          {trend}
        </div>
      </div>
      <div className="w-full bg-muted rounded-full h-2 mt-1">
        <div
          className={cn(
            "h-2 rounded-full transition-all duration-500",
            level === "High" ? "bg-destructive" : level === "Medium" ? "bg-yellow-500" : "bg-green-500"
          )}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
};

export default CongestionIndicator;
