
import React, { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";

interface TrafficGraphProps {
  data: { time: string; [key: string]: string | number }[];
  className?: string;
}

const TrafficGraph = ({ data, className }: TrafficGraphProps) => {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  // Determine which data keys to display (excluding the time key)
  const dataKeys = Object.keys(data[0] || {}).filter(key => key !== 'time');

  // Define colors for each intersection
  const colors = {
    "count": "hsl(var(--primary))",
    "Main Street": "hsl(var(--primary))",
    "Park Avenue": "hsl(200, 100%, 50%)"
  };

  return (
    <div className={cn("p-4 rounded-xl glass flex flex-col gap-4", className)}>
      <div className="text-xs uppercase tracking-wider font-medium text-muted-foreground">
        Traffic Flow (Last Hour)
      </div>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={data}
            margin={{
              top: 10,
              right: 30,
              left: 0,
              bottom: 0,
            }}
          >
            <defs>
              {dataKeys.map((key, index) => (
                <linearGradient key={key} id={`color${key.replace(/\s+/g, '')}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={colors[key as keyof typeof colors] || `hsl(${index * 60}, 70%, 50%)`} stopOpacity={0.8} />
                  <stop offset="95%" stopColor={colors[key as keyof typeof colors] || `hsl(${index * 60}, 70%, 50%)`} stopOpacity={0.1} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis
              dataKey="time"
              stroke="hsl(var(--muted-foreground))"
              fontSize={12}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              stroke="hsl(var(--muted-foreground))"
              fontSize={12}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(var(--card))",
                borderColor: "hsl(var(--border))",
                borderRadius: "var(--radius)",
                fontSize: "14px",
              }}
            />
            {dataKeys.length > 1 && <Legend />}
            
            {dataKeys.map((key, index) => (
              <Area
                key={key}
                type="monotone"
                dataKey={key}
                name={key}
                stroke={colors[key as keyof typeof colors] || `hsl(${index * 60}, 70%, 50%)`}
                fillOpacity={1}
                fill={`url(#color${key.replace(/\s+/g, '')})`}
                animationDuration={1000}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default TrafficGraph;
