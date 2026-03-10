import React, { useState, useEffect } from "react";
import Navigation from "@/components/Navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Camera, Settings2, Wifi, WifiOff, Save, Plus, Trash2 } from "lucide-react";
import {
  fetchCameraConfigs,
  configureCamera,
  addIntersection,
  removeIntersection,
  CameraConfig,
} from "@/lib/api";
import { toast } from "sonner";

const Settings = () => {
  const [cameras, setCameras] = useState<CameraConfig[]>([]);
  const [loading, setLoading] = useState(false);

  // Form state for existing intersections
  const [configs, setConfigs] = useState<Record<string, { source: string; type: "usb" | "ip" | "rtsp" }>>({});

  // New intersection form
  const [newId, setNewId] = useState("");
  const [newName, setNewName] = useState("");
  const [newSource, setNewSource] = useState("0");
  const [newType, setNewType] = useState<"usb" | "ip" | "rtsp">("usb");
  const [addingNew, setAddingNew] = useState(false);

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

  useEffect(() => {
    loadCameras();
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
      await loadCameras();
    }
    setAddingNew(false);
  };

  const handleRemoveIntersection = async (intersectionId: string) => {
    if (!confirm(`Remove intersection ${intersectionId}? This will stop its camera and detection.`)) {
      return;
    }

    const success = await removeIntersection(intersectionId);
    if (success) {
      await loadCameras();
    }
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Navigation />
      <main className="flex-1 container py-6">
        <div className="flex flex-col gap-6 max-w-3xl mx-auto">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">System Settings</h1>
            <p className="text-muted-foreground">Manage intersections, cameras, and hardware</p>
          </div>

          {/* Add New Intersection */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Plus className="h-5 w-5" />
                Add New Intersection
              </CardTitle>
              <CardDescription>
                Add a new intersection with a camera. You can add unlimited intersections.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Intersection ID</Label>
                  <Input
                    placeholder="e.g., int-003"
                    value={newId}
                    onChange={(e) => setNewId(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input
                    placeholder="e.g., Oak Street Intersection"
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label>Camera Type</Label>
                  <Select value={newType} onValueChange={(val) => setNewType(val as any)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
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

          {/* Existing Camera Configuration */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Camera className="h-5 w-5" />
                Camera Configuration
              </CardTitle>
              <CardDescription>
                {cameras.length} intersection{cameras.length !== 1 ? 's' : ''} configured.
                Update camera settings or remove intersections.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {cameras.length === 0 && (
                <p className="text-muted-foreground text-center py-4">
                  No intersections configured yet. Add one above.
                </p>
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
                        <Badge
                          variant={cam.status === "active" ? "default" : "secondary"}
                          className="flex items-center gap-1"
                        >
                          {cam.status === "active" ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
                          {cam.status}
                        </Badge>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveIntersection(cam.intersection_id)}
                          className="text-destructive hover:text-destructive hover:bg-destructive/10"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="space-y-2">
                        <Label>Camera Type</Label>
                        <Select
                          value={config.type}
                          onValueChange={(val) =>
                            setConfigs((prev) => ({
                              ...prev,
                              [cam.intersection_id]: { ...prev[cam.intersection_id], type: val as any },
                            }))
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="usb">USB Camera</SelectItem>
                            <SelectItem value="ip">IP Camera (HTTP)</SelectItem>
                            <SelectItem value="rtsp">RTSP Stream</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>

                      <div className="space-y-2 md:col-span-2">
                        <Label>
                          {config.type === "usb" ? "Camera Index" :
                           config.type === "ip" ? "IP Camera URL" : "RTSP Stream URL"}
                        </Label>
                        <Input
                          placeholder={
                            config.type === "usb" ? "0" :
                            config.type === "ip" ? "http://192.168.1.100:8080/video" :
                            "rtsp://admin:password@192.168.1.100:554/stream"
                          }
                          value={config.source}
                          onChange={(e) =>
                            setConfigs((prev) => ({
                              ...prev,
                              [cam.intersection_id]: { ...prev[cam.intersection_id], source: e.target.value },
                            }))
                          }
                        />
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

          {/* Integration Guide */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings2 className="h-5 w-5" />
                Hardware Integration Guide
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <div className="p-3 rounded-lg bg-muted/50 space-y-2">
                <h4 className="font-semibold">USB Cameras</h4>
                <p className="text-muted-foreground">
                  Connect USB webcams directly. Use camera index 0 for built-in, 1 for first external, etc.
                </p>
              </div>
              <div className="p-3 rounded-lg bg-muted/50 space-y-2">
                <h4 className="font-semibold">IP Cameras (HTTP)</h4>
                <p className="text-muted-foreground">
                  Use the camera's HTTP stream URL. Most IP cameras support MJPEG streams.
                  Example: <code className="bg-muted px-1 py-0.5 rounded text-xs">http://192.168.1.100:8080/video</code>
                </p>
              </div>
              <div className="p-3 rounded-lg bg-muted/50 space-y-2">
                <h4 className="font-semibold">RTSP Streams</h4>
                <p className="text-muted-foreground">
                  For professional cameras, use RTSP protocol.
                  Example: <code className="bg-muted px-1 py-0.5 rounded text-xs">rtsp://admin:pass@192.168.1.100:554/stream1</code>
                </p>
              </div>
              <div className="p-3 rounded-lg bg-primary/5 border border-primary/10 space-y-2">
                <h4 className="font-semibold text-primary">Dynamic Camera Management</h4>
                <ul className="text-muted-foreground list-disc list-inside space-y-1">
                  <li>Add unlimited intersections/cameras at runtime</li>
                  <li>Camera changes take effect immediately (no restart needed)</li>
                  <li>Remove intersections when no longer needed</li>
                  <li>Supports USB, HTTP MJPEG, and RTSP protocols</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
};

export default Settings;
