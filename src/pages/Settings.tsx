import React, { useState, useEffect } from "react";
import Navigation from "@/components/Navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Camera, Settings2, Wifi, WifiOff, Save, Plus, Trash2, Radio, MapPin, Layers, Zap, TestTube } from "lucide-react";
import {
  fetchCameraConfigs,
  configureCamera,
  addIntersection,
  removeIntersection,
  CameraConfig,
  fetchSignalControllers,
  configureSignalController,
  testSignalController,
  SignalControllerStatus,
  fetchZones,
  createZone,
  ZoneInfo,
  fetchIntersections,
  IntersectionInfo,
} from "@/lib/api";
import { toast } from "sonner";

const Settings = () => {
  const [cameras, setCameras] = useState<CameraConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("intersections");

  // Form state for existing intersections
  const [configs, setConfigs] = useState<Record<string, { source: string; type: "usb" | "ip" | "rtsp" }>>({});

  // New intersection form
  const [newId, setNewId] = useState("");
  const [newName, setNewName] = useState("");
  const [newSource, setNewSource] = useState("0");
  const [newType, setNewType] = useState<"usb" | "ip" | "rtsp">("usb");
  const [addingNew, setAddingNew] = useState(false);

  // Signal controllers
  const [signalControllers, setSignalControllers] = useState<SignalControllerStatus>({});
  const [ctrlType, setCtrlType] = useState<Record<string, string>>({});
  const [ctrlEndpoint, setCtrlEndpoint] = useState<Record<string, string>>({});

  // Zones
  const [zones, setZones] = useState<ZoneInfo[]>([]);
  const [intersectionsList, setIntersectionsList] = useState<IntersectionInfo[]>([]);
  const [newZoneId, setNewZoneId] = useState("");
  const [newZoneName, setNewZoneName] = useState("");
  const [selectedZoneIntersections, setSelectedZoneIntersections] = useState<string[]>([]);

  const loadCameras = async () => {
    const data = await fetchCameraConfigs();
    setCameras(data);
    const newConfigs: Record<string, { source: string; type: "usb" | "ip" | "rtsp" }> = {};
    data.forEach((cam) => {
      newConfigs[cam.intersection_id] = {
        source: cam.camera_source,
        type: cam.camera_type,
      };
    });
    setConfigs(newConfigs);
  };

  const loadAll = async () => {
    await Promise.all([
      loadCameras(),
      fetchSignalControllers().then(setSignalControllers),
      fetchZones().then(setZones),
      fetchIntersections().then(setIntersectionsList),
    ]);
  };

  useEffect(() => {
    loadAll();
  }, []);

  const handleSave = async (intersectionId: string) => {
    setLoading(true);
    const config = configs[intersectionId];
    if (config) {
      await configureCamera(intersectionId, config.source, config.type);
      await loadCameras();
    }
    setLoading(false);
  };

  const handleAddIntersection = async () => {
    if (!newId.trim()) {
      toast.error("Intersection ID is required");
      return;
    }
    if (!newName.trim()) {
      toast.error("Intersection name is required");
      return;
    }

    setAddingNew(true);
    const success = await addIntersection(newId.trim(), newName.trim(), newSource, newType);
    if (success) {
      setNewId("");
      setNewName("");
      setNewSource("0");
      setNewType("usb");
      await loadAll();
    }
    setAddingNew(false);
  };

  const handleRemoveIntersection = async (intersectionId: string) => {
    if (!confirm(`Remove intersection ${intersectionId}? This will stop its camera and detection.`)) {
      return;
    }
    const success = await removeIntersection(intersectionId);
    if (success) {
      await loadAll();
    }
  };

  const handleConfigureSignalController = async (intersectionId: string) => {
    const type = ctrlType[intersectionId] || 'http';
    const endpoint = ctrlEndpoint[intersectionId] || '';
    await configureSignalController(intersectionId, { type, endpoint });
    const updated = await fetchSignalControllers();
    setSignalControllers(updated);
  };

  const handleTestSignal = async (intersectionId: string) => {
    await testSignalController(intersectionId, 'green');
  };

  const handleCreateZone = async () => {
    if (!newZoneId.trim() || !newZoneName.trim()) {
      toast.error("Zone ID and name are required");
      return;
    }
    const success = await createZone(newZoneId.trim(), newZoneName.trim(), selectedZoneIntersections);
    if (success) {
      setNewZoneId("");
      setNewZoneName("");
      setSelectedZoneIntersections([]);
      const updated = await fetchZones();
      setZones(updated);
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Navigation />
      <main className="flex-1 container py-6">
        <div className="flex flex-col gap-6 max-w-4xl mx-auto">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">System Settings</h1>
            <p className="text-muted-foreground">Manage intersections, cameras, signal controllers, and zones</p>
          </div>

          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="intersections" className="flex items-center gap-1.5">
                <Camera className="h-4 w-4" />
                Intersections
              </TabsTrigger>
              <TabsTrigger value="signal_controllers" className="flex items-center gap-1.5">
                <Radio className="h-4 w-4" />
                Signal Controllers
              </TabsTrigger>
              <TabsTrigger value="zones" className="flex items-center gap-1.5">
                <Layers className="h-4 w-4" />
                Zones
              </TabsTrigger>
            </TabsList>

            {/* ======= INTERSECTIONS TAB ======= */}
            <TabsContent value="intersections" className="space-y-6 mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Plus className="h-5 w-5" />
                    Add New Intersection
                  </CardTitle>
                  <CardDescription>
                    Add a new intersection with a camera. Scalable to unlimited intersections for city-wide coverage.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Intersection ID</Label>
                      <Input placeholder="e.g., int-003" value={newId} onChange={(e) => setNewId(e.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <Label>Name</Label>
                      <Input placeholder="e.g., Oak Street Intersection" value={newName} onChange={(e) => setNewName(e.target.value)} />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="space-y-2">
                      <Label>Camera Type</Label>
                      <Select value={newType} onValueChange={(val) => setNewType(val as any)}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="usb">USB Camera</SelectItem>
                          <SelectItem value="ip">IP Camera (HTTP)</SelectItem>
                          <SelectItem value="rtsp">RTSP Stream</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2 md:col-span-2">
                      <Label>
                        {newType === "usb" ? "Camera Index (0, 1, 2...)" :
                         newType === "ip" ? "IP Camera URL" : "RTSP Stream URL"}
                      </Label>
                      <Input
                        placeholder={
                          newType === "usb" ? "0" :
                          newType === "ip" ? "http://192.168.1.100:8080/video" :
                          "rtsp://admin:password@192.168.1.100:554/stream"
                        }
                        value={newSource}
                        onChange={(e) => setNewSource(e.target.value)}
                      />
                    </div>
                  </div>

                  <Button onClick={handleAddIntersection} disabled={addingNew}>
                    <Plus className="h-4 w-4 mr-2" />
                    {addingNew ? "Adding..." : "Add Intersection"}
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Camera className="h-5 w-5" />
                    Camera Configuration
                  </CardTitle>
                  <CardDescription>
                    {cameras.length} intersection{cameras.length !== 1 ? 's' : ''} configured.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {cameras.length === 0 && (
                    <p className="text-muted-foreground text-center py-4">No intersections configured yet.</p>
                  )}

                  {cameras.map((cam) => {
                    const config = configs[cam.intersection_id] || { source: "", type: "usb" as const };
                    return (
                      <div key={cam.intersection_id} className="p-4 rounded-lg border space-y-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="font-semibold">{cam.name || cam.intersection_id}</h3>
                            <span className="text-xs text-muted-foreground">ID: {cam.intersection_id}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant={cam.status === "active" ? "default" : "secondary"} className="flex items-center gap-1">
                              {cam.status === "active" ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
                              {cam.status}
                            </Badge>
                            <Button variant="ghost" size="sm" onClick={() => handleRemoveIntersection(cam.intersection_id)}
                              className="text-destructive hover:text-destructive hover:bg-destructive/10">
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div className="space-y-2">
                            <Label>Camera Type</Label>
                            <Select value={config.type} onValueChange={(val) =>
                              setConfigs((prev) => ({ ...prev, [cam.intersection_id]: { ...prev[cam.intersection_id], type: val as any } }))
                            }>
                              <SelectTrigger><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value="usb">USB Camera</SelectItem>
                                <SelectItem value="ip">IP Camera</SelectItem>
                                <SelectItem value="rtsp">RTSP Stream</SelectItem>
                              </SelectContent>
                            </Select>
                          </div>
                          <div className="space-y-2 md:col-span-2">
                            <Label>{config.type === "usb" ? "Camera Index" : config.type === "ip" ? "IP Camera URL" : "RTSP URL"}</Label>
                            <Input value={config.source} onChange={(e) =>
                              setConfigs((prev) => ({ ...prev, [cam.intersection_id]: { ...prev[cam.intersection_id], source: e.target.value } }))
                            } />
                          </div>
                        </div>

                        <Button onClick={() => handleSave(cam.intersection_id)} disabled={loading} size="sm">
                          <Save className="h-4 w-4 mr-2" />
                          Save & Restart Camera
                        </Button>
                      </div>
                    );
                  })}
                </CardContent>
              </Card>
            </TabsContent>

            {/* ======= SIGNAL CONTROLLERS TAB ======= */}
            <TabsContent value="signal_controllers" className="space-y-6 mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Radio className="h-5 w-5" />
                    Traffic Signal Hardware Controllers
                  </CardTitle>
                  <CardDescription>
                    Connect to physical traffic signal controllers via HTTP REST API, MQTT, or GPIO.
                    The system sends signal commands (red/yellow/green) to hardware after AI decisions.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {intersectionsList.length === 0 ? (
                    <p className="text-muted-foreground text-center py-4">
                      No intersections configured. Add intersections first.
                    </p>
                  ) : (
                    intersectionsList.map((int) => {
                      const ctrl = signalControllers[int.id];
                      return (
                        <div key={int.id} className="p-4 rounded-lg border space-y-4">
                          <div className="flex items-center justify-between">
                            <div>
                              <h3 className="font-semibold">{int.name}</h3>
                              <span className="text-xs text-muted-foreground">ID: {int.id}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              {ctrl ? (
                                <Badge variant={ctrl.status === 'connected' ? 'default' : ctrl.status === 'error' ? 'destructive' : 'secondary'}>
                                  <Zap className="h-3 w-3 mr-1" />
                                  {ctrl.status} ({ctrl.total_commands} sent)
                                </Badge>
                              ) : (
                                <Badge variant="outline">Not configured</Badge>
                              )}
                            </div>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div className="space-y-2">
                              <Label>Controller Type</Label>
                              <Select
                                value={ctrlType[int.id] || ctrl?.type || 'http'}
                                onValueChange={(val) => setCtrlType(prev => ({ ...prev, [int.id]: val }))}
                              >
                                <SelectTrigger><SelectValue /></SelectTrigger>
                                <SelectContent>
                                  <SelectItem value="http">HTTP REST API</SelectItem>
                                  <SelectItem value="mqtt">MQTT</SelectItem>
                                  <SelectItem value="gpio">GPIO (Raspberry Pi)</SelectItem>
                                  <SelectItem value="mock">Mock (Testing)</SelectItem>
                                </SelectContent>
                              </Select>
                            </div>
                            <div className="space-y-2 md:col-span-2">
                              <Label>Endpoint URL / Broker</Label>
                              <Input
                                placeholder="http://192.168.1.x:8080/signal"
                                value={ctrlEndpoint[int.id] || ''}
                                onChange={(e) => setCtrlEndpoint(prev => ({ ...prev, [int.id]: e.target.value }))}
                              />
                            </div>
                          </div>

                          <div className="flex gap-2">
                            <Button size="sm" onClick={() => handleConfigureSignalController(int.id)}>
                              <Save className="h-4 w-4 mr-2" />
                              Save Controller
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => handleTestSignal(int.id)}>
                              <TestTube className="h-4 w-4 mr-2" />
                              Test Signal
                            </Button>
                          </div>
                        </div>
                      );
                    })
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Settings2 className="h-5 w-5" />
                    Signal Controller Integration Guide
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4 text-sm">
                  <div className="p-3 rounded-lg bg-muted/50 space-y-2">
                    <h4 className="font-semibold">HTTP REST API</h4>
                    <p className="text-muted-foreground">
                      The system sends POST requests with JSON payload: <code className="bg-muted px-1 py-0.5 rounded text-xs">
                      {`{"intersection_id": "int-001", "signal": "green", "priority": "normal"}`}</code>
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-muted/50 space-y-2">
                    <h4 className="font-semibold">MQTT</h4>
                    <p className="text-muted-foreground">
                      Publishes to topic <code className="bg-muted px-1 py-0.5 rounded text-xs">traffic/signals/&lt;intersection_id&gt;</code>
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-muted/50 space-y-2">
                    <h4 className="font-semibold">GPIO (Raspberry Pi)</h4>
                    <p className="text-muted-foreground">
                      Controls physical LEDs via BCM pins. Default: Red=17, Yellow=27, Green=22
                    </p>
                  </div>
                  <div className="p-3 rounded-lg bg-primary/5 border border-primary/10 space-y-2">
                    <h4 className="font-semibold text-primary">How It Works</h4>
                    <ol className="text-muted-foreground list-decimal list-inside space-y-1">
                      <li>Camera captures live traffic video at the intersection</li>
                      <li>YOLOv11 detects and classifies vehicles in real-time</li>
                      <li>AI calculates PCE density and optimal signal timing</li>
                      <li>Signal command is sent to the physical traffic light controller</li>
                      <li>Emergency vehicles trigger immediate green corridor</li>
                    </ol>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* ======= ZONES TAB ======= */}
            <TabsContent value="zones" className="space-y-6 mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Plus className="h-5 w-5" />
                    Create Traffic Zone
                  </CardTitle>
                  <CardDescription>
                    Group intersections into zones for coordinated traffic control across city regions.
                    Emergency green corridors can be activated per zone.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Zone ID</Label>
                      <Input placeholder="e.g., zone-downtown" value={newZoneId} onChange={(e) => setNewZoneId(e.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <Label>Zone Name</Label>
                      <Input placeholder="e.g., Downtown District" value={newZoneName} onChange={(e) => setNewZoneName(e.target.value)} />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Intersections in Zone</Label>
                    <div className="flex flex-wrap gap-2">
                      {intersectionsList.map(int => (
                        <Button
                          key={int.id}
                          variant={selectedZoneIntersections.includes(int.id) ? "default" : "outline"}
                          size="sm"
                          onClick={() => {
                            setSelectedZoneIntersections(prev =>
                              prev.includes(int.id) ? prev.filter(id => id !== int.id) : [...prev, int.id]
                            );
                          }}
                        >
                          <MapPin className="h-3 w-3 mr-1" />
                          {int.name}
                        </Button>
                      ))}
                    </div>
                    {selectedZoneIntersections.length > 0 && (
                      <p className="text-xs text-muted-foreground">{selectedZoneIntersections.length} intersection(s) selected</p>
                    )}
                  </div>

                  <Button onClick={handleCreateZone}>
                    <Plus className="h-4 w-4 mr-2" />
                    Create Zone
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Layers className="h-5 w-5" />
                    Traffic Zones
                  </CardTitle>
                  <CardDescription>{zones.length} zone{zones.length !== 1 ? 's' : ''} configured</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {zones.length === 0 ? (
                    <p className="text-muted-foreground text-center py-4">
                      No zones created yet. Zones help coordinate traffic signals across city regions.
                    </p>
                  ) : (
                    zones.map(zone => (
                      <div key={zone.id} className="p-4 rounded-lg border space-y-3">
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="font-semibold">{zone.name}</h3>
                            <span className="text-xs text-muted-foreground">ID: {zone.id}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant="outline">{zone.intersection_count} intersections</Badge>
                            {zone.emergency_corridor_active && (
                              <Badge variant="destructive" className="animate-pulse">Emergency Corridor</Badge>
                            )}
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {zone.intersection_ids.map(intId => {
                            const int = intersectionsList.find(i => i.id === intId);
                            return (
                              <Badge key={intId} variant="secondary" className="text-xs">
                                {int?.name || intId}
                              </Badge>
                            );
                          })}
                        </div>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </main>
    </div>
  );
};

export default Settings;
