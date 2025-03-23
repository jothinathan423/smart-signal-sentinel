
import React, { useState } from "react";
import Navigation from "@/components/Navigation";
import Intersection from "@/components/Intersection";
import TrafficGraph from "@/components/TrafficGraph";
import CameraFeed from "@/components/CameraFeed";
import ViolationsList from "@/components/ViolationsList";
import { useTrafficData } from "@/hooks/useTrafficData";
import { Button } from "@/components/ui/button";
import { RefreshCw, AlertTriangle, FileWarning, Scan, Camera, ArrowLeftRight } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const Dashboard = () => {
  const { 
    intersections, 
    historyData, 
    loading, 
    error, 
    updateTrafficStatus, 
    cameraUrls,
    violations,
    loadingViolations,
    checkViolations,
    refreshViolations,
    toggleAutoTrafficControl
  } = useTrafficData();
  
  const [checkingViolations, setCheckingViolations] = useState(false);
  const [activeTab, setActiveTab] = useState<string>("status");
  const [activeIntersection, setActiveIntersection] = useState<string>("int-001");
  const [viewMode, setViewMode] = useState<"split" | "single">("split");
  
  // Check if any intersection has an emergency
  const hasEmergency = intersections.some(int => int.emergency);

  const handleCheckViolations = async (intersectionId: string) => {
    setCheckingViolations(true);
    try {
      await checkViolations(intersectionId);
    } finally {
      setCheckingViolations(false);
    }
  };

  const handleAutoModeChange = async (id: string, enabled: boolean) => {
    await toggleAutoTrafficControl(id, enabled);
  };

  // Create data for graph
  const graphData = historyData.map(point => ({
    time: point.time,
    "Main Street": point.int1Count,
    "Park Avenue": point.int2Count
  }));
  
  // Get intersection objects
  const intersection1 = intersections.find(int => int.id === "int-001");
  const intersection2 = intersections.find(int => int.id === "int-002");

  return (
    <div className="min-h-screen flex flex-col">
      <Navigation />
      
      <main className="flex-1 container py-6">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">Traffic Dashboard</h1>
              <p className="text-muted-foreground">Real-time monitoring of two synchronized intersections</p>
            </div>
            
            <div className="flex items-center gap-4">
              {hasEmergency && (
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

          {loading && intersections.length === 0 && (
            <div className="text-center py-8">
              <div className="animate-spin h-8 w-8 mx-auto border-4 border-primary border-t-transparent rounded-full mb-4"></div>
              <p className="text-muted-foreground">Connecting to cameras and traffic data...</p>
            </div>
          )}

          {/* Toggle for view mode */}
          <div className="flex justify-end mb-4">
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => setViewMode(viewMode === "split" ? "single" : "split")}
              className="flex items-center gap-2"
            >
              <ArrowLeftRight className="h-4 w-4" />
              {viewMode === "split" ? "Single View" : "Split View"}
            </Button>
          </div>

          {viewMode === "split" ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* First Intersection */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Camera className="h-5 w-5" />
                      Main Street Intersection
                    </div>
                    <Badge 
                      variant="outline" 
                      className={intersection1?.status === "green" ? "bg-traffic-green/10 text-traffic-green" : 
                                 intersection1?.status === "yellow" ? "bg-traffic-yellow/10 text-yellow-800" : 
                                 "bg-traffic-red/10 text-traffic-red"}
                    >
                      {intersection1?.status?.toUpperCase() || "UNKNOWN"}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <CameraFeed 
                    cameraUrl={cameraUrls["int-001"] || ''} 
                    title="Main Street Camera" 
                  />
                  
                  {intersection1 && (
                    <Intersection
                      {...intersection1}
                      onStatusChange={updateTrafficStatus}
                      onAutoModeChange={handleAutoModeChange}
                    />
                  )}
                  
                  <Button 
                    onClick={() => handleCheckViolations("int-001")} 
                    disabled={checkingViolations || !intersection1}
                    variant="default"
                    className="w-full bg-destructive hover:bg-destructive/90 text-destructive-foreground"
                  >
                    <Scan className="h-4 w-4 mr-2" />
                    Check for Violations
                  </Button>
                </CardContent>
              </Card>
              
              {/* Second Intersection */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Camera className="h-5 w-5" />
                      Park Avenue Intersection
                    </div>
                    <Badge 
                      variant="outline" 
                      className={intersection2?.status === "green" ? "bg-traffic-green/10 text-traffic-green" : 
                                 intersection2?.status === "yellow" ? "bg-traffic-yellow/10 text-yellow-800" : 
                                 "bg-traffic-red/10 text-traffic-red"}
                    >
                      {intersection2?.status?.toUpperCase() || "UNKNOWN"}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <CameraFeed 
                    cameraUrl={cameraUrls["int-002"] || ''} 
                    title="Park Avenue Camera" 
                  />
                  
                  {intersection2 && (
                    <Intersection
                      {...intersection2}
                      onStatusChange={updateTrafficStatus}
                      onAutoModeChange={handleAutoModeChange}
                    />
                  )}
                  
                  <Button 
                    onClick={() => handleCheckViolations("int-002")} 
                    disabled={checkingViolations || !intersection2}
                    variant="default"
                    className="w-full bg-destructive hover:bg-destructive/90 text-destructive-foreground"
                  >
                    <Scan className="h-4 w-4 mr-2" />
                    Check for Violations
                  </Button>
                </CardContent>
              </Card>
            </div>
          ) : (
            <Tabs value={activeIntersection} onValueChange={setActiveIntersection} className="space-y-4">
              <TabsList className="w-full grid grid-cols-2">
                <TabsTrigger value="int-001">Main Street Intersection</TabsTrigger>
                <TabsTrigger value="int-002">Park Avenue Intersection</TabsTrigger>
              </TabsList>
              
              <TabsContent value="int-001" className="space-y-4">
                {renderIntersectionContent("int-001", intersection1)}
              </TabsContent>
              
              <TabsContent value="int-002" className="space-y-4">
                {renderIntersectionContent("int-002", intersection2)}
              </TabsContent>
            </Tabs>
          )}
          
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
                  <TrafficGraph data={graphData} />
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
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">Detection Parameters</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="p-3 bg-red-50 rounded-lg border border-red-100">
                    <h4 className="font-medium text-red-700 text-sm">Two-Wheeler Violations</h4>
                    <ul className="text-xs text-red-600 mt-1 space-y-1 list-disc pl-4">
                      <li>No helmet detection</li>
                      <li>Multiple passengers (&gt;2)</li>
                    </ul>
                  </div>
                  
                  <div className="p-3 bg-amber-50 rounded-lg border border-amber-100">
                    <h4 className="font-medium text-amber-700 text-sm">Traffic Violations</h4>
                    <ul className="text-xs text-amber-600 mt-1 space-y-1 list-disc pl-4">
                      <li>Red light running</li>
                      <li>Speeding detection</li>
                    </ul>
                  </div>
                  
                  <div className="p-3 bg-blue-50 rounded-lg border border-blue-100">
                    <h4 className="font-medium text-blue-700 text-sm">Coordination Logic</h4>
                    <p className="text-xs text-blue-600 mt-1">
                      {intersection1?.autoMode && intersection2?.autoMode
                        ? "Both intersections in auto-coordination mode"
                        : intersection1?.autoMode || intersection2?.autoMode
                        ? "Partial coordination active"
                        : "Manual control mode active"}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
  
  function renderIntersectionContent(intersectionId: string, intersection: any) {
    return (
      <>
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-2">
            <CameraFeed 
              cameraUrl={cameraUrls[intersectionId] || ''} 
              title={`${intersection?.name || 'Loading...'} Camera`} 
            />
          </div>
          
          <div className="lg:col-span-2">
            <div className="flex flex-col gap-4">
              {intersection ? (
                <Intersection
                  key={intersection.id}
                  {...intersection}
                  onStatusChange={updateTrafficStatus}
                  onAutoModeChange={handleAutoModeChange}
                />
              ) : !loading ? (
                <div className="flex flex-col items-center justify-center py-12 bg-muted/20 rounded-xl">
                  <div className="bg-muted p-4 rounded-full mb-4">
                    <AlertTriangle className="h-6 w-6 text-muted-foreground" />
                  </div>
                  <h3 className="text-lg font-medium">No Traffic Data</h3>
                  <p className="text-muted-foreground text-center max-w-md mt-2">
                    There is no traffic data available for this intersection. Please ensure the backend server is running and camera is accessible.
                  </p>
                </div>
              ) : (
                <div className="rounded-xl bg-muted/10 p-6 flex items-center justify-center">
                  <div className="animate-spin h-6 w-6 border-4 border-primary border-t-transparent rounded-full mr-3"></div>
                  <span>Loading intersection data...</span>
                </div>
              )}
              
              <Button 
                onClick={() => handleCheckViolations(intersectionId)} 
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
      </>
    );
  }
};

export default Dashboard;
