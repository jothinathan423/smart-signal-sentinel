import React, { useState, useEffect } from "react";
import Navigation from "@/components/Navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Camera, Settings2, Wifi, WifiOff, Save } from "lucide-react";
import { configureCamera, fetchCameraConfigs, CameraConfig } from "@/lib/api";
import { toast } from "sonner";

const Settings = () => {
  const [cameras, setCameras] = useState<CameraConfig[]>([]);
  const [loading, setLoading] = useState(false);

  // Form state for two intersections
  const [configs, setConfigs] = useState<Record<string, { source: string; type: "usb" | "ip" | "rtsp" }>>({
    "int-001": { source: "0", type: "usb" },
    "int-002": { source: "1", type: "usb" },
  });

  useEffect(() => {
    const load = async () => {
      const data = await fetchCameraConfigs();
      setCameras(data);
      // Pre-fill form from loaded configs
      data.forEach((cam) => {
        setConfigs((prev) => ({
          ...prev,
          [cam.intersection_id]: {
            source: cam.camera_source,
            type: cam.camera_type,
          },
        }));
      });
    };
    load();
  }, []);

  const handleSave = async (intersectionId: string) => {
    setLoading(true);
    const config = configs[intersectionId];
    const success = await configureCamera(intersectionId, config.source, config.type);
    if (success) {
      const data = await fetchCameraConfigs();
      setCameras(data);
    }
    setLoading(false);
  };

  const intersections = [
    { id: "int-001", name: "Main Street Intersection" },
    { id: "int-002", name: "Park Avenue Intersection" },
  ];

  return (
    <div className="min-h-screen flex flex-col">
      <Navigation />
      <main className="flex-1 container py-6">
        <div className="flex flex-col gap-6 max-w-3xl mx-auto">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">System Settings</h1>
            <p className="text-muted-foreground">Configure cameras and hardware integration</p>
          </div>

          {/* Camera Configuration */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Camera className="h-5 w-5" />
                Camera Configuration
              </CardTitle>
              <CardDescription>
                Configure USB cameras, IP cameras, or RTSP streams for each intersection.
                Supports any IP camera with HTTP or RTSP streaming.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {intersections.map(({ id, name }) => {
                const config = configs[id] || { source: "", type: "usb" };
                const camStatus = cameras.find((c) => c.intersection_id === id);
                return (
                  <div key={id} className="p-4 rounded-lg border space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="font-semibold">{name}</h3>
                      <Badge variant={camStatus?.status === "active" ? "default" : "secondary"} className="flex items-center gap-1">
                        {camStatus?.status === "active" ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
                        {camStatus?.status || "Not configured"}
                      </Badge>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="space-y-2">
                        <Label>Camera Type</Label>
                        <Select
                          value={config.type}
                          onValueChange={(val) =>
                            setConfigs((prev) => ({
                              ...prev,
                              [id]: { ...prev[id], type: val as any },
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
                          {config.type === "usb" ? "Camera Index (0, 1, 2...)" : config.type === "ip" ? "IP Camera URL" : "RTSP Stream URL"}
                        </Label>
                        <Input
                          placeholder={
                            config.type === "usb"
                              ? "0"
                              : config.type === "ip"
                              ? "http://192.168.1.100:8080/video"
                              : "rtsp://admin:password@192.168.1.100:554/stream"
                          }
                          value={config.source}
                          onChange={(e) =>
                            setConfigs((prev) => ({
                              ...prev,
                              [id]: { ...prev[id], source: e.target.value },
                            }))
                          }
                        />
                      </div>
                    </div>

                    <Button onClick={() => handleSave(id)} disabled={loading} size="sm">
                      <Save className="h-4 w-4 mr-2" />
                      Save Configuration
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
                <h4 className="font-semibold text-primary">Supported Protocols</h4>
                <ul className="text-muted-foreground list-disc list-inside space-y-1">
                  <li>USB/UVC cameras (DirectShow on Windows, V4L2 on Linux)</li>
                  <li>HTTP MJPEG streams</li>
                  <li>RTSP (H.264/H.265 via GStreamer or FFmpeg)</li>
                  <li>ONVIF-compliant IP cameras</li>
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
