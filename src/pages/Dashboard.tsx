
import { useState } from "react";
import Navigation from "@/components/Navigation";
import Intersection from "@/components/Intersection";
import TrafficGraph from "@/components/TrafficGraph";
import CameraFeed from "@/components/CameraFeed";
import ViolationsList from "@/components/ViolationsList";
import CongestionIndicator from "@/components/CongestionIndicator";
import { useTrafficData } from "@/hooks/useTrafficData";
import { Button } from "@/components/ui/button";
import { RefreshCw, AlertTriangle, FileWarning, Scan, Camera, ArrowLeftRight, Siren, Activity, Car } from "lucide-react";
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
    toggleAutoTrafficControl,
    systemOverview,
  } = useTrafficData();

  const [checkingViolations, setCheckingViolations] = useState(false);
  const [activeTab, setActiveTab] = useState<string>("all");
  const [bottomTab, setBottomTab] = useState<string>("status");
  const [viewMode, setViewMode] = useState<"split" | "single">("split");
  const [activeIntersection, setActiveIntersection] = useState<string>("");

  // Show all intersections (including connecting/failed cameras with status badges)
  const activeIntersections = intersections;

  const emergencyIntersections = activeIntersections.filter(int => int.emergency);
  const emergencyCount = emergencyIntersections.length;
  const totalEmergencyVehicles = activeIntersections.reduce((sum, int) => sum + (int.emergencyCount || 0), 0);

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
    const entry: { time: string; [key: string]: string | number } = { time: point.time };
    activeIntersections.forEach(int => {
      entry[int.name] = point[int.name] || 0;
    });
    return entry;
  });

  // Set default active intersection
  const currentActiveIntersection = activeIntersection || activeIntersections[0]?.id || "";

  return (
    <div className="min-h-screen flex flex-col">
      <Navigation />

      <main className="flex-1 container py-6">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">Traffic Dashboard</h1>
              <p className="text-muted-foreground">
                Real-time traffic monitoring and control
              </p>
            </div>

            <div className="flex items-center gap-3">
              {totalEmergencyVehicles > 0 && (
                <Badge variant="destructive" className="text-sm px-3 py-1.5 animate-pulse flex items-center gap-1.5">
                  <Siren className="h-4 w-4" />
                  {totalEmergencyVehicles} Emergency
                </Badge>
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

          {loading && activeIntersections.length === 0 && (
            <div className="text-center py-8">
              <div className="animate-spin h-8 w-8 mx-auto border-4 border-primary border-t-transparent rounded-full mb-4"></div>
              <p className="text-muted-foreground">Connecting to cameras and traffic data...</p>
            </div>
          )}

          {!loading && activeIntersections.length === 0 && (
            <div className="text-center py-12 border rounded-lg bg-muted/20">
              <Camera className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium">No Active Cameras</h3>
              <p className="text-muted-foreground mt-2">
                Add traffic cameras in the <strong>Settings</strong> page to start monitoring intersections.
              </p>
            </div>
          )}

          {/* Main Tabs: All Intersections / Emergency */}
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <div className="flex items-center justify-between">
              <TabsList>
                <TabsTrigger value="all">All Intersections</TabsTrigger>
                <TabsTrigger value="emergency" className="flex items-center gap-1.5">
                  Emergency
                  {emergencyCount > 0 && (
                    <span className="bg-destructive text-destructive-foreground text-xs rounded-full px-1.5 py-0.5 min-w-[20px] text-center">
                      {emergencyCount}
                    </span>
                  )}
                </TabsTrigger>
              </TabsList>

              {activeIntersections.length > 1 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setViewMode(viewMode === "split" ? "single" : "split")}
                  className="flex items-center gap-2"
                >
                  <ArrowLeftRight className="h-4 w-4" />
                  {viewMode === "split" ? "Single View" : "Split View"}
                </Button>
              )}
            </div>

            <TabsContent value="all" className="mt-4">
              <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                {/* Intersection Cards - Left 3 cols */}
                <div className="lg:col-span-3">
                  {viewMode === "split" ? (
                    <div className={`grid gap-6 ${
                      activeIntersections.length === 1 ? 'grid-cols-1' :
                      activeIntersections.length <= 2 ? 'grid-cols-1 md:grid-cols-2' :
                      activeIntersections.length <= 3 ? 'grid-cols-1 md:grid-cols-3' :
                      'grid-cols-1 md:grid-cols-2 xl:grid-cols-3'
                    }`}>
                      {activeIntersections.map(intersection => (
                        <Card key={intersection.id} className="overflow-hidden">
                          <CardHeader className="pb-2">
                            <div className="flex items-center justify-between">
                              <CardTitle className="text-lg truncate">{intersection.name}</CardTitle>
                              <div className="flex gap-1">
                                {(["north", "south", "east", "west"] as const).map(dir => {
                                  const sig = intersection.signals?.[dir] || intersection.status || "red";
                                  return (
                                    <Badge key={dir} variant="outline" className={`text-xs px-1.5 py-0.5 ${
                                      sig === "green" ? "bg-traffic-green/10 text-traffic-green border-traffic-green/30" :
                                      sig === "yellow" ? "bg-traffic-yellow/10 text-yellow-800 border-traffic-yellow/30" :
                                      "bg-traffic-red/10 text-traffic-red border-traffic-red/30"
                                    }`}>
                                      {dir[0].toUpperCase()}
                                    </Badge>
                                  );
                                })}
                              </div>
                            </div>
                            <div className="text-xs text-muted-foreground">Last updated: {intersection.lastUpdated}</div>
                          </CardHeader>
                          <CardContent className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                              <div className="p-3 rounded-lg bg-muted/30 space-y-2">
                                <div className="text-xs uppercase tracking-wider font-medium text-muted-foreground">Traffic Signals</div>
                                <div className="grid grid-cols-2 gap-2 mt-1">
                                  {(["north", "south", "east", "west"] as const).map(dir => {
                                    const sig = intersection.signals?.[dir] || "red";
                                    return (
                                      <div key={dir} className="flex flex-col items-center gap-1">
                                        <span className="text-[10px] uppercase font-medium text-muted-foreground">{dir}</span>
                                        <div className="flex gap-1">
                                          <div className={`w-5 h-5 rounded-full ${sig === "red" ? "bg-traffic-red" : "bg-traffic-red/20"}`} />
                                          <div className={`w-5 h-5 rounded-full ${sig === "yellow" ? "bg-traffic-yellow" : "bg-traffic-yellow/20"}`} />
                                          <div className={`w-5 h-5 rounded-full ${sig === "green" ? "bg-traffic-green" : "bg-traffic-green/20"}`} />
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                              <div className="p-3 rounded-lg bg-muted/30 space-y-2">
                                <div className="text-xs uppercase tracking-wider font-medium text-muted-foreground">Vehicle Count</div>
                                <div className="flex items-center gap-2 mt-2">
                                  <Car className="h-6 w-6 text-primary" />
                                  <span className="text-3xl font-bold">{intersection.vehicleCount}</span>
                                </div>
                                {intersection.emergency && (
                                  <div className="text-xs text-traffic-emergency font-medium mt-1 flex items-center gap-1">
                                    <Siren className="h-3 w-3" />
                                    Emergency Vehicle Detected
                                  </div>
                                )}
                              </div>
                            </div>

                            {/* Emergency alert */}
                            {intersection.emergency && (
                              <div className="flex items-center gap-3 p-3 rounded-lg bg-traffic-emergency/10 border border-traffic-emergency/20 animate-pulse">
                                <div className="bg-traffic-emergency text-white p-2 rounded-full">
                                  <Siren className="w-5 h-5" />
                                </div>
                                <div className="flex-1">
                                  <h4 className="font-medium text-traffic-emergency text-sm">Emergency Vehicle Detected</h4>
                                  <p className="text-xs text-muted-foreground">Traffic signal priority activated</p>
                                </div>
                                <AlertTriangle className="w-5 h-5 text-traffic-emergency" />
                              </div>
                            )}

                            {/* Signal controls */}
                            <div className="flex items-center justify-between">
                              <div className="text-xs text-muted-foreground">ID: {intersection.id}</div>
                              <div className="flex gap-1.5">
                                {(["red", "yellow", "green"] as const).map(sig => (
                                  <Button
                                    key={sig}
                                    variant="outline"
                                    size="sm"
                                    className={intersection.status === sig ?
                                      sig === "red" ? "bg-traffic-red/10 border-traffic-red/30 text-traffic-red" :
                                      sig === "yellow" ? "bg-traffic-yellow/10 border-traffic-yellow/30 text-yellow-800" :
                                      "bg-traffic-green/10 border-traffic-green/30 text-traffic-green"
                                      : ""}
                                    onClick={() => updateTrafficStatus(intersection.id, sig)}
                                    disabled={intersection.autoMode}
                                  >
                                    {sig.charAt(0).toUpperCase() + sig.slice(1)}
                                  </Button>
                                ))}
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      ))}
                    </div>
                  ) : (
                    /* Single View - tabs for each intersection */
                    activeIntersections.length > 0 && (
                      <Tabs value={currentActiveIntersection} onValueChange={setActiveIntersection} className="space-y-4">
                        <TabsList className="w-full flex flex-wrap">
                          {activeIntersections.map(int => (
                            <TabsTrigger key={int.id} value={int.id} className="flex-1">{int.name}</TabsTrigger>
                          ))}
                        </TabsList>

                        {activeIntersections.map(intersection => (
                          <TabsContent key={intersection.id} value={intersection.id} className="space-y-4">
                            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                              <CameraFeed
                                cameraUrl={cameraUrls[intersection.id] || ''}
                                title={`${intersection.name} Camera`}
                              />
                              <div className="flex flex-col gap-4">
                                <Intersection
                                  {...intersection}
                                  onStatusChange={updateTrafficStatus}
                                  onAutoModeChange={handleAutoModeChange}
                                />
                                <CongestionIndicator vehicleCount={intersection.vehicleCount} />
                                <Button
                                  onClick={() => handleCheckViolations(intersection.id)}
                                  disabled={checkingViolations}
                                  variant="default"
                                  className="bg-destructive hover:bg-destructive/90 text-destructive-foreground"
                                >
                                  <Scan className="h-4 w-4 mr-2" />
                                  Check for Violations
                                </Button>
                              </div>
                            </div>
                          </TabsContent>
                        ))}
                      </Tabs>
                    )
                  )}
                </div>

                {/* Right sidebar - Traffic flow chart + System status */}
                <div className="lg:col-span-1 space-y-4">
                  <TrafficGraph data={graphData} className="h-auto" />

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm uppercase tracking-wider text-muted-foreground">System Status</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                      <div className="flex items-center justify-between py-1.5">
                        <span className="text-sm">Monitored Intersections</span>
                        <span className="font-bold">{systemOverview?.monitored_intersections || activeIntersections.length}</span>
                      </div>
                      <div className="flex items-center justify-between py-1.5">
                        <span className="text-sm">Emergency Vehicles</span>
                        <span className="font-bold text-traffic-emergency">{systemOverview?.emergency_vehicles || totalEmergencyVehicles}</span>
                      </div>
                      <div className="flex items-center justify-between py-1.5">
                        <span className="text-sm">Total Vehicles</span>
                        <span className="font-bold">{systemOverview?.total_vehicles || activeIntersections.reduce((s, i) => s + i.vehicleCount, 0)}</span>
                      </div>
                      <div className="flex items-center justify-between py-1.5">
                        <span className="text-sm">Active Cameras</span>
                        <span className="font-bold">{systemOverview?.active_cameras || 0}</span>
                      </div>
                      <div className="flex items-center justify-between py-1.5">
                        <span className="text-sm">Auto Mode</span>
                        <span className="font-bold">{systemOverview?.auto_mode_count || activeIntersections.filter(i => i.autoMode).length}</span>
                      </div>
                      <div className="flex items-center justify-between py-1.5">
                        <span className="text-sm">Signal Controllers</span>
                        <span className="font-bold">{systemOverview?.signal_controllers || 0}</span>
                      </div>
                      <div className="flex items-center justify-between py-1.5">
                        <span className="text-sm">Total PCE Density</span>
                        <span className="font-bold">{systemOverview?.total_pce_density || 0}</span>
                      </div>
                      {systemOverview?.cuda_available && (
                        <Badge variant="outline" className="mt-2 bg-green-50 text-green-700 border-green-200">
                          GPU Accelerated
                        </Badge>
                      )}
                    </CardContent>
                  </Card>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="emergency" className="mt-4">
              {emergencyIntersections.length === 0 ? (
                <Card>
                  <CardContent className="py-12 text-center">
                    <Activity className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                    <h3 className="text-lg font-medium">No Emergency Vehicles Detected</h3>
                    <p className="text-muted-foreground mt-2">
                      The system monitors all intersections for emergency vehicles in real-time.
                      Green corridors are automatically created when detected.
                    </p>
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-4">
                  <div className="bg-traffic-emergency/10 border border-traffic-emergency/20 rounded-lg p-4 flex items-center gap-3">
                    <Siren className="h-6 w-6 text-traffic-emergency" />
                    <div>
                      <h3 className="font-medium text-traffic-emergency">
                        {totalEmergencyVehicles} Emergency Vehicle{totalEmergencyVehicles !== 1 ? 's' : ''} Active
                      </h3>
                      <p className="text-sm text-muted-foreground">
                        Green corridors have been automatically activated at {emergencyCount} intersection{emergencyCount !== 1 ? 's' : ''}
                      </p>
                    </div>
                  </div>

                  <div className="grid gap-4 grid-cols-1 md:grid-cols-2">
                    {emergencyIntersections.map(intersection => (
                      <Card key={intersection.id} className="border-traffic-emergency/30">
                        <CardHeader className="pb-2">
                          <div className="flex items-center justify-between">
                            <CardTitle className="text-lg">{intersection.name}</CardTitle>
                            <Badge variant="destructive" className="animate-pulse">
                              <Siren className="h-3 w-3 mr-1" />
                              EMERGENCY
                            </Badge>
                          </div>
                        </CardHeader>
                        <CardContent className="space-y-3">
                          <div className="grid grid-cols-2 gap-3">
                            <div className="p-3 rounded-lg bg-traffic-green/10 text-center">
                              <div className="text-xs text-muted-foreground">Signal</div>
                              <div className="text-lg font-bold text-traffic-green">GREEN</div>
                              <div className="text-xs text-muted-foreground">Priority Active</div>
                            </div>
                            <div className="p-3 rounded-lg bg-muted/30 text-center">
                              <div className="text-xs text-muted-foreground">Vehicles</div>
                              <div className="text-2xl font-bold">{intersection.vehicleCount}</div>
                            </div>
                          </div>
                          <CameraFeed
                            cameraUrl={cameraUrls[intersection.id] || ''}
                            title={`${intersection.name} - Emergency Feed`}
                          />
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              )}
            </TabsContent>
          </Tabs>

          {/* Bottom section: Traffic History / Violations */}
          <Tabs value={bottomTab} onValueChange={setBottomTab}>
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
      </main>
    </div>
  );
};

export default Dashboard;
