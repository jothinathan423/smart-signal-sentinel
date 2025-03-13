
import React, { useState } from "react";
import Navigation from "@/components/Navigation";
import Intersection from "@/components/Intersection";
import TrafficGraph from "@/components/TrafficGraph";
import { useTrafficData } from "@/hooks/useTrafficData";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { RefreshCw, AlertTriangle } from "lucide-react";

const Dashboard = () => {
  const { intersections, historyData, loading, error, updateTrafficStatus } = useTrafficData();
  const [activeTab, setActiveTab] = useState("all");

  const filteredIntersections = activeTab === "all" 
    ? intersections 
    : activeTab === "emergency" 
      ? intersections.filter(i => i.emergency) 
      : intersections;

  const emergencyCount = intersections.filter(i => i.emergency).length;

  return (
    <div className="min-h-screen flex flex-col">
      <Navigation />
      
      <main className="flex-1 container py-6">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold tracking-tight">Traffic Dashboard</h1>
              <p className="text-muted-foreground">Real-time traffic monitoring and control</p>
            </div>
            
            <div className="flex items-center gap-4">
              {emergencyCount > 0 && (
                <div className="bg-traffic-emergency/10 text-traffic-emergency px-3 py-1.5 rounded-lg flex items-center gap-2 animate-emergency-pulse">
                  <AlertTriangle className="h-4 w-4" />
                  <span className="font-medium">{emergencyCount} Emergency</span>
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

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
            <div className="lg:col-span-3 space-y-6">
              <Tabs defaultValue="all" className="w-full" value={activeTab} onValueChange={setActiveTab}>
                <TabsList>
                  <TabsTrigger value="all">All Intersections</TabsTrigger>
                  <TabsTrigger value="emergency" className="relative">
                    Emergency
                    {emergencyCount > 0 && (
                      <span className="absolute -top-1 -right-1 bg-traffic-emergency text-white rounded-full w-5 h-5 flex items-center justify-center text-xs">
                        {emergencyCount}
                      </span>
                    )}
                  </TabsTrigger>
                </TabsList>
                <TabsContent value="all" className="space-y-4 mt-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {filteredIntersections.map((intersection) => (
                      <Intersection
                        key={intersection.id}
                        {...intersection}
                        onStatusChange={updateTrafficStatus}
                      />
                    ))}
                  </div>
                </TabsContent>
                <TabsContent value="emergency" className="space-y-4 mt-4">
                  {filteredIntersections.length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {filteredIntersections.map((intersection) => (
                        <Intersection
                          key={intersection.id}
                          {...intersection}
                          onStatusChange={updateTrafficStatus}
                        />
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-12">
                      <div className="bg-muted p-4 rounded-full mb-4">
                        <AlertTriangle className="h-6 w-6 text-muted-foreground" />
                      </div>
                      <h3 className="text-lg font-medium">No Emergency Vehicles</h3>
                      <p className="text-muted-foreground text-center max-w-md mt-2">
                        There are currently no emergency vehicles detected at any monitored intersections.
                      </p>
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            </div>
            
            <div className="lg:col-span-1 space-y-6">
              <TrafficGraph data={historyData} />
              
              <div className="rounded-xl glass p-4 space-y-3">
                <div className="text-xs uppercase tracking-wider font-medium text-muted-foreground">
                  System Status
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-sm">Monitored Intersections</span>
                    <span className="font-mono">{intersections.length}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm">Emergency Vehicles</span>
                    <span className="font-mono">{emergencyCount}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm">Total Vehicles</span>
                    <span className="font-mono">
                      {intersections.reduce((sum, i) => sum + i.vehicleCount, 0)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-sm">Last Update</span>
                    <span className="font-mono text-xs">
                      {new Date().toLocaleTimeString()}
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
