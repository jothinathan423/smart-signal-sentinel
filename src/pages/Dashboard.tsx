
import React from "react";
import Navigation from "@/components/Navigation";
import Intersection from "@/components/Intersection";
import TrafficGraph from "@/components/TrafficGraph";
import { useTrafficData } from "@/hooks/useTrafficData";
import { Button } from "@/components/ui/button";
import { RefreshCw, AlertTriangle } from "lucide-react";

const Dashboard = () => {
  const { intersections, historyData, loading, error, updateTrafficStatus } = useTrafficData();
  
  // Get the single intersection or null if none
  const intersection = intersections.length > 0 ? intersections[0] : null;
  const emergency = intersection?.emergency || false;

  return (
    <div className="min-h-screen flex flex-col">
      <Navigation />
      
      <main className="flex-1 container py-6">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">Traffic Dashboard</h1>
              <p className="text-muted-foreground">Real-time traffic monitoring using laptop camera</p>
            </div>
            
            <div className="flex items-center gap-4">
              {emergency && (
                <div className="bg-traffic-emergency/10 text-traffic-emergency px-3 py-1.5 rounded-lg flex items-center gap-2 animate-emergency-pulse">
                  <AlertTriangle className="h-4 w-4" />
                  <span className="font-medium">Emergency Vehicle Detected</span>
                </div>
              )}
              <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
            </div>
          </div>

          {error && (
            <div className="bg-destructive/10 text-destructive px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          {loading && !intersection && (
            <div className="text-center py-8">
              <div className="animate-spin h-8 w-8 mx-auto border-4 border-primary border-t-transparent rounded-full mb-4"></div>
              <p className="text-muted-foreground">Connecting to camera and traffic data...</p>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <div className="lg:col-span-3 space-y-6">
              {intersection ? (
                <Intersection
                  key={intersection.id}
                  {...intersection}
                  onStatusChange={updateTrafficStatus}
                />
              ) : !loading ? (
                <div className="flex flex-col items-center justify-center py-12 bg-muted/20 rounded-xl">
                  <div className="bg-muted p-4 rounded-full mb-4">
                    <AlertTriangle className="h-6 w-6 text-muted-foreground" />
                  </div>
                  <h3 className="text-lg font-medium">No Traffic Data</h3>
                  <p className="text-muted-foreground text-center max-w-md mt-2">
                    There is no traffic data available. Please ensure the backend server is running and your laptop camera is accessible.
                  </p>
                </div>
              ) : null}
            </div>
            
            <div className="lg:col-span-1 space-y-6">
              <TrafficGraph data={historyData} />
              
              <div className="rounded-xl glass p-4 space-y-3">
                <div className="text-xs uppercase tracking-wider font-medium text-muted-foreground">
                  System Status
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-sm">Traffic Signal</span>
                    <span className="font-mono">{intersection?.status || "N/A"}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm">Emergency Vehicle</span>
                    <span className="font-mono">{intersection?.emergency ? "Detected" : "None"}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm">Vehicle Count</span>
                    <span className="font-mono">
                      {intersection?.vehicleCount || 0}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm">Last Update</span>
                    <span className="font-mono text-xs">
                      {intersection?.lastUpdated || new Date().toLocaleTimeString()}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Dashboard;
