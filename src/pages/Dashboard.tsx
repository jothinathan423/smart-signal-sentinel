
import React, { useState } from "react";
import Navigation from "@/components/Navigation";
import Intersection from "@/components/Intersection";
import TrafficGraph from "@/components/TrafficGraph";
import CameraFeed from "@/components/CameraFeed";
import ViolationsList from "@/components/ViolationsList";
import CongestionIndicator from "@/components/CongestionIndicator";
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
  const [viewMode, setViewMode] = useState<"split" | "single">("split");
  const [activeIntersection, setActiveIntersection] = useState<string>("");

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

  // Build graph data dynamically from whatever intersections exist
  const graphData = historyData.map(point => {
    const entry: Record<string, string | number> = { time: point.time };
    intersections.forEach(int => {
      entry[int.name] = point[int.name] || 0;
    });
    return entry;
  });

  // Set default active intersection
  const currentActiveIntersection = activeIntersection || intersections[0]?.id || "";

  return (
    <div className="min-h-screen flex flex-col">
      <Navigation />

      <main className="flex-1 container py-6">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">Traffic Dashboard</h1>
              <p className="text-muted-foreground">
                Real-time monitoring of {intersections.length} intersection{intersections.length !== 1 ? 's' : ''}
              </p>
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

          {/* Congestion Summary - dynamic grid */}
          {intersections.length > 0 && (
            <div className={`grid gap-4 ${
              intersections.length === 1 ? 'grid-cols-1' :
              intersections.length === 2 ? 'grid-cols-1 sm:grid-cols-2' :
              intersections.length === 3 ? 'grid-cols-1 sm:grid-cols-3' :
              'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4'
            }`}>
              {intersections.map(int => (
                <CongestionIndicator
                  key={int.id}
                  vehicleCount={int.vehicleCount}
                />
              ))}
            </div>
          )}

          {/* Toggle for view mode */}
          {intersections.length > 1 && (
            <div className="flex justify-end">
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
          )}

          {viewMode === "split" ? (
            /* Split View - dynamic grid of all intersections */
            <div className={`grid gap-6 ${
              intersections.length === 1 ? 'grid-cols-1' :
              intersections.length <= 2 ? 'grid-cols-1 lg:grid-cols-2' :
              intersections.length <= 3 ? 'grid-cols-1 lg:grid-cols-3' :
              'grid-cols-1 lg:grid-cols-2 xl:grid-cols-3'
            }`}>
              {intersections.map(intersection => (
                <Card key={intersection.id}>
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Camera className="h-5 w-5" />
                        <span className="truncate">{intersection.name}</span>
                      </div>
                      <Badge
                        variant="outline"
                        className={intersection.status === "green" ? "bg-traffic-green/10 text-traffic-green" :
                                   intersection.status === "yellow" ? "bg-traffic-yellow/10 text-yellow-800" :
                                   "bg-traffic-red/10 text-traffic-red"}
                      >
                        {intersection.status?.toUpperCase() || "UNKNOWN"}
                      </Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <CameraFeed
                      cameraUrl={cameraUrls[intersection.id] || ''}
                      title={`${intersection.name} Camera`}
                    />

                    <Intersection
                      {...intersection}
                      onStatusChange={updateTrafficStatus}
                      onAutoModeChange={handleAutoModeChange}
                    />

                    <Button
                      onClick={() => handleCheckViolations(intersection.id)}
                      disabled={checkingViolations}
                      variant="default"
                      className="w-full bg-destructive hover:bg-destructive/90 text-destructive-foreground"
                    >
                      <Scan className="h-4 w-4 mr-2" />
                      Check for Violations
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            /* Single View - tabs for each intersection */
            intersections.length > 0 && (
              <Tabs value={currentActiveIntersection} onValueChange={setActiveIntersection} className="space-y-4">
                <TabsList className={`w-full grid grid-cols-${Math.min(intersections.length, 4)}`}>
                  {intersections.map(int => (
                    <TabsTrigger key={int.id} value={int.id}>{int.name}</TabsTrigger>
                  ))}
                </TabsList>

                {intersections.map(intersection => (
                  <TabsContent key={intersection.id} value={intersection.id} className="space-y-4">
                    {renderIntersectionContent(intersection.id, intersection)}
                  </TabsContent>
                ))}
              </Tabs>
            )
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
                  <CardTitle className="text-sm">System Status</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="p-3 rounded-lg bg-destructive/5 border border-destructive/10">
                    <h4 className="font-medium text-destructive text-sm">Violation Detection</h4>
                    <ul className="text-xs text-muted-foreground mt-1 space-y-1 list-disc pl-4">
                      <li>Red light crossing</li>
                      <li>Speeding detection</li>
                      <li>No helmet (AI vision)</li>
                      <li>Excess passengers</li>
                    </ul>
                  </div>

                  <div className="p-3 rounded-lg bg-primary/5 border border-primary/10">
                    <h4 className="font-medium text-primary text-sm">AI Features</h4>
                    <ul className="text-xs text-muted-foreground mt-1 space-y-1 list-disc pl-4">
                      <li>YOLOv11 vehicle detection</li>
                      <li>Online pattern learning</li>
                      <li>Predictive signal timing</li>
                      <li>Speed tracking</li>
                    </ul>
                  </div>

                  <div className="p-3 rounded-lg bg-accent border border-border">
                    <h4 className="font-medium text-sm">Intersections</h4>
                    <p className="text-xs text-muted-foreground mt-1">
                      {intersections.length} active intersection{intersections.length !== 1 ? 's' : ''}
                      {intersections.filter(i => i.autoMode).length > 0 &&
                        ` (${intersections.filter(i => i.autoMode).length} in auto mode)`}
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
                <>
                  <Intersection
                    key={intersection.id}
                    {...intersection}
                    onStatusChange={updateTrafficStatus}
                    onAutoModeChange={handleAutoModeChange}
                  />
                  <CongestionIndicator vehicleCount={intersection.vehicleCount} />
                </>
              ) : !loading ? (
                <div className="flex flex-col items-center justify-center py-12 bg-muted/20 rounded-xl">
                  <div className="bg-muted p-4 rounded-full mb-4">
                    <AlertTriangle className="h-6 w-6 text-muted-foreground" />
                  </div>
                  <h3 className="text-lg font-medium">No Traffic Data</h3>
                  <p className="text-muted-foreground text-center max-w-md mt-2">
                    No traffic data available. Please ensure the backend server is running.
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
