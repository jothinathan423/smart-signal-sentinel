
import React from "react";
import Navigation from "@/components/Navigation";
import { Separator } from "@/components/ui/separator";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, Camera, Brain, Shield, Gauge, Database, Settings2, Workflow, Target, Rocket } from "lucide-react";

const About = () => {
  const features = [
    {
      icon: <Camera className="h-5 w-5" />,
      title: "Traffic Density Detection",
      items: [
        "YOLOv11-based real-time vehicle detection from camera feeds",
        "Vehicle counting and classification (car, truck, bus, motorcycle)",
        "PCE (Passenger Car Equivalent) weighted density estimation",
        "Dynamic multi-camera support with add/remove at runtime",
      ],
    },
    {
      icon: <Gauge className="h-5 w-5" />,
      title: "Dynamic Traffic Signal Control",
      items: [
        "No fixed timers — signals adjust based on real-time vehicle density",
        "Higher traffic lanes receive longer green signals",
        "Coordinated signal switching between intersections",
        "Predictive timing using AI-learned traffic patterns",
      ],
    },
    {
      icon: <Shield className="h-5 w-5" />,
      title: "Emergency Vehicle Priority",
      items: [
        "Automatic emergency vehicle detection via color analysis",
        "Instant green signal priority for emergency lane",
        "Coordinated red signals for cross-traffic",
        "Reduced waiting time for ambulances and fire trucks",
      ],
    },
    {
      icon: <Brain className="h-5 w-5" />,
      title: "AI & Online Learning",
      items: [
        "Online & Continual Learning — model adapts without retraining",
        "Traffic pattern memory indexed by hour of day",
        "Exponential moving average for smooth pattern updates",
        "Predictive signal timing with confidence scoring",
      ],
    },
    {
      icon: <Target className="h-5 w-5" />,
      title: "Traffic Violation Detection",
      items: [
        "Red light crossing detection via stop-line tracking",
        "Real speed calculation from vehicle displacement",
        "Helmet detection using color & shape analysis",
        "Excess passenger detection on two-wheelers",
      ],
    },
    {
      icon: <Database className="h-5 w-5" />,
      title: "Data Storage & Analysis",
      items: [
        "MongoDB for persistent violation and pattern storage",
        "Peak hour analysis and congestion pattern detection",
        "Exportable traffic reports (JSON format)",
        "Learning logs for AI model audit trail",
      ],
    },
    {
      icon: <Settings2 className="h-5 w-5" />,
      title: "Hardware Integration",
      items: [
        "USB/UVC camera support (laptop & external webcams)",
        "IP camera integration via HTTP MJPEG streams",
        "RTSP stream support for professional cameras",
        "ONVIF-compliant camera compatibility",
      ],
    },
  ];

  const workflow = [
    "Cameras capture live video at each intersection",
    "YOLO model detects and classifies vehicles in real-time",
    "System calculates traffic density, speed, and violations",
    "AI learns traffic patterns and adjusts signal timing",
    "Signals are dynamically coordinated across intersections",
    "Dashboard displays real-time data for monitoring",
    "Violations and patterns are stored in the database",
    "Reports are generated for traffic management authorities",
  ];

  const outcomes = [
    "Reduced traffic congestion through AI-based signal control",
    "Improved vehicle flow with predictive timing",
    "Faster emergency vehicle movement with green corridors",
    "Automated violation detection for road safety",
    "Data-driven traffic management decisions",
  ];

  const futureEnhancements = [
    "Advanced AI traffic prediction with deep learning",
    "Integration with smart city infrastructure (IoT sensors)",
    "Mobile application for traffic alerts and navigation",
    "License plate recognition (ANPR) integration",
    "Federated learning across multiple city intersections",
  ];

  return (
    <div className="min-h-screen flex flex-col">
      <Navigation />
      
      <main className="flex-1 container py-6">
        <div className="max-w-4xl mx-auto space-y-8 animate-fade-in">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">About the System</h1>
            <p className="text-muted-foreground mt-2">
              Centralized AI-Based Smart Traffic Management System Using YOLO with Online and Continual Learning
            </p>
          </div>
          
          <Separator />
          
          <div className="space-y-4">
            <h2 className="text-2xl font-semibold">Overview</h2>
            <p className="text-muted-foreground leading-relaxed">
              This system implements a Centralized AI-Based Smart Traffic Management architecture where live video
              streams from multiple intersections are transmitted to a central control unit. It uses YOLOv11 deep learning
              for real-time vehicle detection with PCE-weighted density estimation, integrates Online and Continual Learning
              for adaptive pattern recognition, dynamically adjusts signal timings based on traffic density, detects
              emergency vehicles for automatic green corridor creation, and identifies traffic violations using AI-based
              video analysis. A centralized MongoDB database stores all data for real-time monitoring and long-term
              traffic analysis.
            </p>
          </div>

          <Separator />

          <div className="space-y-4">
            <h2 className="text-2xl font-semibold">System Components</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {features.map((feature, idx) => (
                <Card key={idx}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base flex items-center gap-2">
                      <div className="p-2 rounded-lg bg-primary/10 text-primary">{feature.icon}</div>
                      {feature.title}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-1.5">
                      {feature.items.map((item, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-muted-foreground">
                          <CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                          {item}
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>

          <Separator />

          <div className="space-y-4">
            <h2 className="text-2xl font-semibold flex items-center gap-2">
              <Workflow className="h-6 w-6" />
              System Workflow
            </h2>
            <div className="space-y-3">
              {workflow.map((step, i) => (
                <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-muted/30">
                  <div className="h-6 w-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-bold shrink-0">
                    {i + 1}
                  </div>
                  <p className="text-sm">{step}</p>
                </div>
              ))}
            </div>
          </div>

          <Separator />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <h2 className="text-2xl font-semibold flex items-center gap-2">
                <Target className="h-6 w-6" />
                Expected Outcomes
              </h2>
              <ul className="space-y-2">
                {outcomes.map((outcome, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <CheckCircle2 className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                    {outcome}
                  </li>
                ))}
              </ul>
            </div>

            <div className="space-y-4">
              <h2 className="text-2xl font-semibold flex items-center gap-2">
                <Rocket className="h-6 w-6" />
                Future Enhancements
              </h2>
              <ul className="space-y-2">
                {futureEnhancements.map((item, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <Badge variant="outline" className="text-xs shrink-0 mt-0.5">{i + 1}</Badge>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <Separator />

          <div className="space-y-4">
            <h2 className="text-2xl font-semibold">Technical Stack</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { name: "React + TypeScript", desc: "Frontend" },
                { name: "Python + Flask", desc: "Backend" },
                { name: "YOLOv11", desc: "Detection" },
                { name: "MongoDB", desc: "Database" },
                { name: "OpenCV", desc: "Vision" },
                { name: "Recharts", desc: "Visualization" },
                { name: "Tailwind CSS", desc: "Styling" },
                { name: "Online Learning", desc: "AI Adaptation" },
              ].map((tech, i) => (
                <div key={i} className="p-3 rounded-lg border text-center">
                  <div className="font-medium text-sm">{tech.name}</div>
                  <div className="text-xs text-muted-foreground">{tech.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </main>
      
      <footer className="border-t py-6 md:py-0">
        <div className="container flex flex-col items-center justify-between gap-4 md:h-24 md:flex-row">
          <p className="text-center text-sm leading-loose text-muted-foreground md:text-left">
            © 2025 Centralized AI-Based Smart Traffic Management System. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
};

export default About;
