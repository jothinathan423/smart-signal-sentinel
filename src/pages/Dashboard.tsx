
import React, { useState } from "react";
import Navigation from "@/components/Navigation";
import Intersection from "@/components/Intersection";
import TrafficGraph from "@/components/TrafficGraph";
import CameraFeed from "@/components/CameraFeed";
import ViolationsList from "@/components/ViolationsList";
import { useTrafficData } from "@/hooks/useTrafficData";
import { Button } from "@/components/ui/button";
import { RefreshCw, AlertTriangle, FileWarning, Scan } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const Dashboard = () => {
  const { 
    intersections, 
    historyData, 
    loading, 
    error, 
    updateTrafficStatus, 
    cameraUrl,
    violations,
    loadingViolations,
    checkViolations,
    refreshViolations
  } = useTrafficData();
  
  const [checkingViolations, setCheckingViolations] = useState(false);
  const [activeTab, setActiveTab] = useState<string>("status");
  
  // Get the single intersection or null if none
  const intersection = intersections.length > 0 ? intersections[0] : null;
  const emergency = intersection?.emergency || false;

  const handleCheckViolations = async () => {
    setCheckingViolations(true);
    try {
      await checkViolations();
    } finally {
      setCheckingViolations(false);
    }
  };

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
            <div className="lg:col-span-2">
              <CameraFeed cameraUrl={cameraUrl} title="Live Traffic Camera" />
            </div>
            
            <div className="lg:col-span-2">
              <div className="flex flex-col gap-4">
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
                
                <Button 
                  onClick={handleCheckViolations} 
                  disabled={checkingViolations || !intersection}
                  variant="default"
                  className="bg-destructive hover:bg-destructive/90 text-destructive-foreground"
                >
                  {checkingViolations ? (
                    <>
                      <div className="animate-spin h-4 w-4 border-2 border-current border-t-transparent rounded-full mr-2"></div>
                      Scanning for violations...
                    </>
                  ) : (
                    <>
                      <Scan className="h-4 w-4 mr-2" />
                      Check for Traffic Violations
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
          
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <div className="lg:col-span-3">
              <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="mb-4">
                  <TabsTrigger value="status">Traffic History</TabsTrigger>
                  <TabsTrigger value="violations" className="flex items-center gap-1.5">
                    <FileWarning className="h-4 w-4" />
                    Violations
                    {violations.length > 0 && (
                      <span className="bg-destructive/20 text-destructive text-xs px-1.5 py-0.5 rounded-full">
                        {violations.length}
                      </span>
                    )}
                  </TabsTrigger>
                </TabsList>
                
                <TabsContent value="status" className="mt-0">
                  <TrafficGraph data={historyData} />
                </TabsContent>
                
                <TabsContent value="violations" className="mt-0">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold">Recent Traffic Violations</h3>
                    <Button 
                      variant="outline" 
                      size="sm" 
                      onClick={refreshViolations}
                      disabled={loadingViolations}
                    >
                      <RefreshCw className={`h-4 w-4 mr-2 ${loadingViolations ? 'animate-spin' : ''}`} />
                      Refresh
                    </Button>
                  </div>
                  <ViolationsList violations={violations} isLoading={loadingViolations} />
                </TabsContent>
              </Tabs>
            </div>
            
            <div className="lg:col-span-1">
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
                  <div className="flex justify-between items-center">
                    <span className="text-sm">Violations</span>
                    <span className="font-mono">
                      {violations.length}
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
