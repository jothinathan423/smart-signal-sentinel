import React, { useState, useEffect, useCallback } from "react";
import Navigation from "@/components/Navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { RefreshCw, TrendingUp, Clock, Gauge, Brain, Download, BarChart3, Activity } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, Legend, PieChart, Pie, Cell } from "recharts";
import { fetchTrafficPatterns, fetchSpeedData, fetchLearningLogs, TrafficPatternData, SpeedData, LearningLog } from "@/lib/api";
import { toast } from "sonner";

const COLORS = ["hsl(210, 100%, 50%)", "hsl(200, 100%, 50%)", "hsl(150, 70%, 45%)", "hsl(40, 90%, 55%)"];

const Analytics = () => {
  const [patterns, setPatterns] = useState<TrafficPatternData | null>(null);
  const [speedData, setSpeedData] = useState<SpeedData | null>(null);
  const [learningLogs, setLearningLogs] = useState<LearningLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("patterns");

  const loadData = useCallback(async () => {
    setLoading(true);
    const [p, s, l] = await Promise.all([
      fetchTrafficPatterns(),
      fetchSpeedData(),
      fetchLearningLogs(),
    ]);
    setPatterns(p);
    setSpeedData(s);
    setLearningLogs(l);
    setLoading(false);
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 15000);
    return () => clearInterval(interval);
  }, [loadData]);

  // Transform pattern data for hourly chart
  const getHourlyChartData = () => {
    if (!patterns) return [];
    const data = [];
    for (let h = 0; h < 24; h++) {
      const point: Record<string, any> = {
        hour: `${h.toString().padStart(2, "0")}:00`,
      };
      for (const [id, intData] of Object.entries(patterns)) {
        const name = id === "int-001" ? "Main Street" : "Park Avenue";
        const hourData = intData.patterns[h.toString()];
        point[name] = hourData ? Math.round(hourData.avg_count * 10) / 10 : 0;
        point[`${name}_peak`] = hourData?.peak_detected || false;
      }
      data.push(point);
    }
    return data;
  };

  // Get peak hours
  const getPeakHours = () => {
    if (!patterns) return [];
    const peaks: { intersection: string; hour: number; avgCount: number }[] = [];
    for (const [id, intData] of Object.entries(patterns)) {
      const name = id === "int-001" ? "Main Street" : "Park Avenue";
      for (const [hour, data] of Object.entries(intData.patterns)) {
        if (data.peak_detected) {
          peaks.push({ intersection: name, hour: parseInt(hour), avgCount: Math.round(data.avg_count * 10) / 10 });
        }
      }
    }
    return peaks;
  };

  // Get violation type distribution from learning logs
  const getViolationDistribution = () => {
    const dist: Record<string, number> = {};
    learningLogs.forEach((log) => {
      if (log.event_type === "pattern_update") {
        const key = log.intersection_id === "int-001" ? "Main Street" : "Park Avenue";
        dist[key] = (dist[key] || 0) + 1;
      }
    });
    return Object.entries(dist).map(([name, value]) => ({ name, value }));
  };

  const handleExportReport = () => {
    const report = {
      generated_at: new Date().toISOString(),
      traffic_patterns: patterns,
      speed_data: speedData,
      peak_hours: getPeakHours(),
      learning_events: learningLogs.length,
    };
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `traffic-report-${new Date().toISOString().split("T")[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success("Report exported successfully");
  };

  const hourlyData = getHourlyChartData();
  const peakHours = getPeakHours();

  return (
    <div className="min-h-screen flex flex-col">
      <Navigation />
      <main className="flex-1 container py-6">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">Traffic Analytics</h1>
              <p className="text-muted-foreground">Data analysis, patterns, and reports</p>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={loadData} disabled={loading}>
                <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
                Refresh
              </Button>
              <Button variant="default" size="sm" onClick={handleExportReport}>
                <Download className="h-4 w-4 mr-2" />
                Export Report
              </Button>
            </div>
          </div>

          {/* Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Predictions */}
            {patterns && Object.entries(patterns).map(([id, data]) => {
              const name = id === "int-001" ? "Main St" : "Park Ave";
              const pred = data.predictions;
              return (
                <Card key={id}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <TrendingUp className="h-4 w-4 text-primary" />
                      {name} Prediction
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{Math.round(pred.next_hour_prediction)} vehicles</div>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant={pred.trend === "increasing" ? "destructive" : pred.trend === "decreasing" ? "secondary" : "outline"}>
                        {pred.trend}
                      </Badge>
                      <span className="text-xs text-muted-foreground">{(pred.confidence * 100).toFixed(0)}% confidence</span>
                    </div>
                    {pred.is_peak_hour && (
                      <Badge className="mt-2 bg-destructive/10 text-destructive border-destructive/20" variant="outline">
                        Peak Hour
                      </Badge>
                    )}
                  </CardContent>
                </Card>
              );
            })}

            {/* Speed Stats */}
            {speedData && Object.entries(speedData).map(([id, data]) => {
              const name = id === "int-001" ? "Main St" : "Park Ave";
              return (
                <Card key={`speed-${id}`}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <Gauge className="h-4 w-4 text-primary" />
                      {name} Speed
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{data.average_speed.toFixed(1)} km/h</div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Max: {data.max_speed.toFixed(1)} km/h | Limit: {data.speed_limit} km/h
                    </div>
                    {data.speeding_count > 0 && (
                      <Badge className="mt-2" variant="destructive">
                        {data.speeding_count} speeding
                      </Badge>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>

          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="patterns" className="flex items-center gap-1.5">
                <BarChart3 className="h-4 w-4" />
                Traffic Patterns
              </TabsTrigger>
              <TabsTrigger value="peaks" className="flex items-center gap-1.5">
                <Clock className="h-4 w-4" />
                Peak Analysis
              </TabsTrigger>
              <TabsTrigger value="learning" className="flex items-center gap-1.5">
                <Brain className="h-4 w-4" />
                AI Learning Logs
              </TabsTrigger>
            </TabsList>

            <TabsContent value="patterns" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle>Hourly Traffic Density Pattern</CardTitle>
                  <CardDescription>Average vehicle count learned over time per hour of day</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="h-80">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={hourlyData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                        <XAxis dataKey="hour" fontSize={11} stroke="hsl(var(--muted-foreground))" />
                        <YAxis fontSize={12} stroke="hsl(var(--muted-foreground))" />
                        <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))", borderRadius: "var(--radius)" }} />
                        <Legend />
                        <Bar dataKey="Main Street" fill="hsl(210, 100%, 50%)" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="Park Avenue" fill="hsl(200, 100%, 50%)" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="peaks" className="mt-4 space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Detected Peak Hours</CardTitle>
                    <CardDescription>Hours with above-average traffic (auto-detected by AI)</CardDescription>
                  </CardHeader>
                  <CardContent>
                    {peakHours.length === 0 ? (
                      <p className="text-muted-foreground text-sm py-4">No peak hours detected yet. The system needs more data samples to identify patterns.</p>
                    ) : (
                      <div className="space-y-2">
                        {peakHours.map((p, i) => (
                          <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-muted/50">
                            <div className="flex items-center gap-2">
                              <Clock className="h-4 w-4 text-destructive" />
                              <span className="font-medium">{`${p.hour.toString().padStart(2, "0")}:00`}</span>
                              <span className="text-muted-foreground text-sm">— {p.intersection}</span>
                            </div>
                            <Badge variant="destructive">~{p.avgCount} vehicles</Badge>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Learning Activity Distribution</CardTitle>
                    <CardDescription>Pattern updates per intersection</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie data={getViolationDistribution()} cx="50%" cy="50%" innerRadius={60} outerRadius={80} paddingAngle={5} dataKey="value" label>
                            {getViolationDistribution().map((_, i) => (
                              <Cell key={i} fill={COLORS[i % COLORS.length]} />
                            ))}
                          </Pie>
                          <Tooltip />
                          <Legend />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Congestion Summary */}
              <Card>
                <CardHeader>
                  <CardTitle>Congestion Level Summary</CardTitle>
                  <CardDescription>Current traffic congestion assessment by intersection</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {patterns && Object.entries(patterns).map(([id, data]) => {
                      const name = id === "int-001" ? "Main Street" : "Park Avenue";
                      const avg = data.predictions.current_hour_avg || 0;
                      const level = avg > 15 ? "High" : avg > 8 ? "Medium" : "Low";
                      const levelColor = level === "High" ? "destructive" : level === "Medium" ? "secondary" : "outline";
                      return (
                        <div key={id} className="p-4 rounded-lg border bg-card space-y-3">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold">{name}</span>
                            <Badge variant={levelColor as any}>{level} Congestion</Badge>
                          </div>
                          <div className="w-full bg-muted rounded-full h-3">
                            <div
                              className={`h-3 rounded-full transition-all ${level === "High" ? "bg-destructive" : level === "Medium" ? "bg-yellow-500" : "bg-green-500"}`}
                              style={{ width: `${Math.min(100, (avg / 25) * 100)}%` }}
                            />
                          </div>
                          <div className="text-xs text-muted-foreground">
                            Current avg: {avg.toFixed(1)} vehicles | Trend: {data.predictions.trend}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="learning" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Brain className="h-5 w-5 text-primary" />
                    Online & Continual Learning Logs
                  </CardTitle>
                  <CardDescription>
                    Recent AI model learning events — pattern updates, predictions, and adaptive adjustments
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {learningLogs.length === 0 ? (
                    <p className="text-muted-foreground text-sm py-4">No learning events recorded yet. The system learns as it processes traffic data.</p>
                  ) : (
                    <div className="max-h-96 overflow-y-auto space-y-2">
                      {learningLogs.slice(0, 50).map((log, i) => (
                        <div key={log.id || i} className="flex items-start gap-3 p-3 rounded-lg bg-muted/30 text-sm">
                          <Activity className="h-4 w-4 text-primary mt-0.5 shrink-0" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <Badge variant="outline" className="text-xs">
                                {log.event_type}
                              </Badge>
                              <span className="text-xs text-muted-foreground">
                                {log.intersection_id === "int-001" ? "Main Street" : "Park Avenue"}
                              </span>
                              <span className="text-xs text-muted-foreground ml-auto">
                                {new Date(log.timestamp).toLocaleTimeString()}
                              </span>
                            </div>
                            {log.data && (
                              <div className="text-xs text-muted-foreground mt-1">
                                {log.data.hour !== undefined && `Hour: ${log.data.hour}`}
                                {log.data.vehicle_count !== undefined && ` | Vehicles: ${log.data.vehicle_count}`}
                                {log.data.new_avg !== undefined && ` | New Avg: ${log.data.new_avg.toFixed(1)}`}
                                {log.data.samples !== undefined && ` | Samples: ${log.data.samples}`}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
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

export default Analytics;
