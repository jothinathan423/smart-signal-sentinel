
import { useState, useEffect, useCallback } from "react";
import Navigation from "@/components/Navigation";
import CameraFeed from "@/components/CameraFeed";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Play, Square, Plus, Trash2, Car, Truck, Bus, Bike,
  Siren, RefreshCw, Gauge, Users
} from "lucide-react";
import {
  fetchSimulations, createSimulation, updateSimulation, deleteSimulation,
  spawnSimVehicle, clearSimVehicles, fetchSimulationStatus,
  getCameraStreamUrl, SimulationConfig,
} from "@/lib/api";
import { toast } from "sonner";

const VEHICLE_TYPES = [
  { type: "car", label: "Car", icon: Car, color: "bg-blue-500" },
  { type: "truck", label: "Truck", icon: Truck, color: "bg-red-700" },
  { type: "bus", label: "Bus", icon: Bus, color: "bg-orange-500" },
  { type: "motorcycle", label: "Motorcycle", icon: Bike, color: "bg-cyan-500" },
  { type: "bicycle", label: "Bicycle", icon: Bike, color: "bg-green-500" },
  { type: "ambulance", label: "Ambulance", icon: Siren, color: "bg-red-500" },
];

const DIRECTIONS = ["north", "south", "east", "west"];

const Simulation = () => {
  const [simulations, setSimulations] = useState<SimulationConfig[]>([]);
  const [selectedSim, setSelectedSim] = useState<string>("");
  const [simStatus, setSimStatus] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  // New simulation form
  const [newSimId, setNewSimId] = useState("sim-001");
  const [newSimName, setNewSimName] = useState("Test Intersection");

  // Spawn controls
  const [spawnType, setSpawnType] = useState("car");
  const [spawnDirection, setSpawnDirection] = useState("north");
  const [spawnSpeed, setSpawnSpeed] = useState(40);

  // Config controls
  const [autoSpawn, setAutoSpawn] = useState(true);
  const [spawnRate, setSpawnRate] = useState(2);
  const [defaultSpeed, setDefaultSpeed] = useState(40);

  const loadSimulations = useCallback(async () => {
    const data = await fetchSimulations();
    setSimulations(data);
    if (data.length > 0 && !selectedSim) {
      setSelectedSim(data[0].id);
    }
  }, [selectedSim]);

  const loadStatus = useCallback(async () => {
    if (!selectedSim) return;
    const status = await fetchSimulationStatus(selectedSim);
    if (status) {
      setSimStatus(status);
      setAutoSpawn(status.auto_spawn);
      setSpawnRate(status.spawn_rate);
      setDefaultSpeed(status.default_speed);
    }
  }, [selectedSim]);

  useEffect(() => {
    loadSimulations();
  }, [loadSimulations]);

  useEffect(() => {
    if (!selectedSim) return;
    loadStatus();
    const interval = setInterval(loadStatus, 2000);
    return () => clearInterval(interval);
  }, [selectedSim, loadStatus]);

  const handleCreate = async () => {
    if (!newSimId.trim()) {
      toast.error("Enter an intersection ID");
      return;
    }
    setLoading(true);
    const success = await createSimulation(newSimId.trim(), {
      name: newSimName.trim() || newSimId.trim(),
      auto_spawn: autoSpawn,
      spawn_rate: spawnRate,
      default_speed: defaultSpeed,
    });
    if (success) {
      setSelectedSim(newSimId.trim());
      await loadSimulations();
    }
    setLoading(false);
  };

  const handleDelete = async (id: string) => {
    await deleteSimulation(id);
    if (selectedSim === id) setSelectedSim("");
    setSimStatus(null);
    await loadSimulations();
  };

  const handleSpawn = async () => {
    if (!selectedSim) return;
    await spawnSimVehicle(selectedSim, {
      type: spawnType,
      direction: spawnDirection,
      speed: spawnSpeed,
    });
  };

  const handleSpawnMultiple = async (count: number) => {
    if (!selectedSim) return;
    for (let i = 0; i < count; i++) {
      await spawnSimVehicle(selectedSim, {});
    }
    toast.success(`Spawned ${count} random vehicles`);
  };

  const handleClear = async () => {
    if (!selectedSim) return;
    await clearSimVehicles(selectedSim);
    toast.success("All vehicles cleared");
  };

  const handleUpdateConfig = async () => {
    if (!selectedSim) return;
    await updateSimulation(selectedSim, {
      auto_spawn: autoSpawn,
      spawn_rate: spawnRate,
      default_speed: defaultSpeed,
    });
    toast.success("Simulation config updated");
  };

  const currentSim = simulations.find(s => s.id === selectedSim);
  const detection = simStatus?.detection;

  return (
    <div className="min-h-screen bg-background">
      <Navigation />
      <main className="container mx-auto p-4 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold">Traffic Simulation</h1>
            <p className="text-muted-foreground">Test the system without real cameras</p>
          </div>
          <Button variant="outline" onClick={loadSimulations}>
            <RefreshCw className="h-4 w-4 mr-2" /> Refresh
          </Button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Controls */}
          <div className="space-y-4">
            {/* Create New Simulation */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Create Simulation</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <Label>Intersection ID</Label>
                  <Input value={newSimId} onChange={e => setNewSimId(e.target.value)}
                    placeholder="e.g. sim-001" />
                </div>
                <div>
                  <Label>Name</Label>
                  <Input value={newSimName} onChange={e => setNewSimName(e.target.value)}
                    placeholder="e.g. Main St & 5th Ave" />
                </div>
                <Button onClick={handleCreate} disabled={loading} className="w-full">
                  <Play className="h-4 w-4 mr-2" /> Start Simulation
                </Button>
              </CardContent>
            </Card>

            {/* Active Simulations */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Active Simulations</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {simulations.length === 0 && (
                  <p className="text-sm text-muted-foreground">No simulations running</p>
                )}
                {simulations.map(sim => (
                  <div key={sim.id}
                    className={`flex items-center justify-between p-2 rounded-lg border cursor-pointer transition-colors ${
                      selectedSim === sim.id ? "border-primary bg-primary/5" : "border-border hover:bg-muted/50"
                    }`}
                    onClick={() => setSelectedSim(sim.id)}
                  >
                    <div>
                      <div className="font-medium text-sm">{sim.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {sim.vehicle_count} vehicles | {sim.total_spawned} spawned
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={sim.running ? "default" : "secondary"}>
                        {sim.running ? "Running" : "Stopped"}
                      </Badge>
                      <Button size="icon" variant="ghost"
                        onClick={e => { e.stopPropagation(); handleDelete(sim.id); }}>
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            {/* Simulation Config */}
            {selectedSim && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-lg">Configuration</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center justify-between">
                    <Label>Auto-spawn vehicles</Label>
                    <Switch checked={autoSpawn} onCheckedChange={setAutoSpawn} />
                  </div>
                  <div>
                    <Label>Spawn rate: {spawnRate.toFixed(1)} vehicles/sec</Label>
                    <Slider value={[spawnRate]} min={0.1} max={10} step={0.1}
                      onValueChange={v => setSpawnRate(v[0])} />
                  </div>
                  <div>
                    <Label>Default speed: {defaultSpeed} km/h</Label>
                    <Slider value={[defaultSpeed]} min={10} max={100} step={5}
                      onValueChange={v => setDefaultSpeed(v[0])} />
                  </div>
                  <Button onClick={handleUpdateConfig} className="w-full" variant="outline">
                    Apply Config
                  </Button>
                </CardContent>
              </Card>
            )}
          </div>

          {/* Center: Live View */}
          <div className="lg:col-span-2 space-y-4">
            {selectedSim ? (
              <>
                {/* Simulation Video Feed */}
                <Card>
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">
                        Live View: {currentSim?.name || selectedSim}
                      </CardTitle>
                      {simStatus?.signal && (
                        <Badge className={
                          simStatus.signal === "green" ? "bg-green-500" :
                          simStatus.signal === "yellow" ? "bg-yellow-500 text-black" :
                          "bg-red-500"
                        }>
                          Signal: {simStatus.signal.toUpperCase()}
                        </Badge>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    <CameraFeed
                      cameraUrl={getCameraStreamUrl(selectedSim, 20)}
                      title={`${currentSim?.name || selectedSim} - Simulation`}
                    />
                  </CardContent>
                </Card>

                {/* Stats */}
                {detection && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <Card>
                      <CardContent className="p-4 text-center">
                        <div className="text-2xl font-bold">{detection.vehicle_count}</div>
                        <div className="text-xs text-muted-foreground">Vehicles</div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-4 text-center">
                        <div className="text-2xl font-bold">{detection.pce_density}</div>
                        <div className="text-xs text-muted-foreground">PCE Density</div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-4 text-center">
                        <div className="text-2xl font-bold">{simStatus?.total_spawned || 0}</div>
                        <div className="text-xs text-muted-foreground">Total Spawned</div>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="p-4 text-center">
                        <div className="text-2xl font-bold text-red-500">{detection.emergency_count}</div>
                        <div className="text-xs text-muted-foreground">Emergency</div>
                      </CardContent>
                    </Card>
                  </div>
                )}

                {/* Spawn Controls */}
                <Tabs defaultValue="manual">
                  <TabsList>
                    <TabsTrigger value="manual">Manual Spawn</TabsTrigger>
                    <TabsTrigger value="quick">Quick Actions</TabsTrigger>
                  </TabsList>

                  <TabsContent value="manual">
                    <Card>
                      <CardContent className="p-4 space-y-4">
                        {/* Vehicle Type Selection */}
                        <div>
                          <Label className="mb-2 block">Vehicle Type</Label>
                          <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                            {VEHICLE_TYPES.map(vt => (
                              <Button key={vt.type} variant={spawnType === vt.type ? "default" : "outline"}
                                size="sm" className="flex flex-col h-auto py-2 gap-1"
                                onClick={() => setSpawnType(vt.type)}>
                                <vt.icon className="h-4 w-4" />
                                <span className="text-xs">{vt.label}</span>
                              </Button>
                            ))}
                          </div>
                        </div>

                        {/* Direction */}
                        <div>
                          <Label className="mb-2 block">Direction</Label>
                          <div className="grid grid-cols-4 gap-2">
                            {DIRECTIONS.map(d => (
                              <Button key={d} variant={spawnDirection === d ? "default" : "outline"}
                                size="sm" onClick={() => setSpawnDirection(d)}>
                                {d.charAt(0).toUpperCase() + d.slice(1)}
                              </Button>
                            ))}
                          </div>
                        </div>

                        {/* Speed */}
                        <div>
                          <Label>Speed: {spawnSpeed} km/h</Label>
                          <Slider value={[spawnSpeed]} min={5} max={100} step={5}
                            onValueChange={v => setSpawnSpeed(v[0])} />
                        </div>

                        <Button onClick={handleSpawn} className="w-full">
                          <Plus className="h-4 w-4 mr-2" /> Spawn {spawnType}
                        </Button>
                      </CardContent>
                    </Card>
                  </TabsContent>

                  <TabsContent value="quick">
                    <Card>
                      <CardContent className="p-4 space-y-3">
                        <div className="grid grid-cols-2 gap-3">
                          <Button onClick={() => handleSpawnMultiple(5)} variant="outline">
                            <Car className="h-4 w-4 mr-2" /> +5 Random Vehicles
                          </Button>
                          <Button onClick={() => handleSpawnMultiple(15)} variant="outline">
                            <Users className="h-4 w-4 mr-2" /> +15 Rush Hour
                          </Button>
                          <Button onClick={() => spawnSimVehicle(selectedSim, { type: "ambulance", speed: 60 })}
                            className="bg-red-500 hover:bg-red-600 text-white">
                            <Siren className="h-4 w-4 mr-2" /> Spawn Ambulance
                          </Button>
                          <Button onClick={() => spawnSimVehicle(selectedSim, { type: "truck", speed: 25 })}
                            variant="outline">
                            <Truck className="h-4 w-4 mr-2" /> Spawn Slow Truck
                          </Button>
                          <Button onClick={() => spawnSimVehicle(selectedSim, { type: "car", speed: 80 })}
                            variant="outline" className="border-red-300">
                            <Gauge className="h-4 w-4 mr-2 text-red-500" /> Spawn Speeding Car
                          </Button>
                          <Button onClick={handleClear} variant="destructive">
                            <Trash2 className="h-4 w-4 mr-2" /> Clear All
                          </Button>
                        </div>

                        {/* Vehicle Type Breakdown */}
                        {detection?.vehicle_type_counts && Object.keys(detection.vehicle_type_counts).length > 0 && (
                          <div className="pt-3 border-t">
                            <Label className="text-sm mb-2 block">Current Vehicles by Type</Label>
                            <div className="flex flex-wrap gap-2">
                              {Object.entries(detection.vehicle_type_counts).map(([type, count]) => (
                                <Badge key={type} variant="secondary">
                                  {type}: {count as number}
                                </Badge>
                              ))}
                            </div>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  </TabsContent>
                </Tabs>
              </>
            ) : (
              <Card className="flex flex-col items-center justify-center min-h-[400px]">
                <CardContent className="text-center p-8">
                  <Play className="h-16 w-16 mx-auto mb-4 text-muted-foreground" />
                  <h3 className="text-xl font-semibold mb-2">No Simulation Running</h3>
                  <p className="text-muted-foreground mb-4">
                    Create a simulation to test the traffic management system without real cameras.
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default Simulation;
