
import React from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowRight, Activity, Shield, Clock } from "lucide-react";
import Navigation from "@/components/Navigation";

const Index = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex flex-col">
      <Navigation />
      
      <main className="flex-1">
        <section className="container py-12 md:py-24 lg:py-32 space-y-8">
          <div className="mx-auto flex flex-col items-center space-y-4 text-center">
            <div className="rounded-full bg-primary/10 p-3 animate-fade-in">
              <Activity className="h-6 w-6 text-primary" />
            </div>
            <h1 className="text-4xl font-bold tracking-tighter sm:text-5xl md:text-6xl/none animate-slide-up">
              Smart Traffic Management System
            </h1>
            <p className="max-w-[700px] text-muted-foreground md:text-xl/relaxed lg:text-base/relaxed xl:text-xl/relaxed animate-slide-up" style={{ animationDelay: "100ms" }}>
              Intelligent traffic monitoring and control system with emergency vehicle detection
            </p>
            <div className="flex flex-wrap items-center justify-center gap-4 animate-slide-up" style={{ animationDelay: "200ms" }}>
              <Button size="lg" onClick={() => navigate("/dashboard")}>
                View Dashboard
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
              <Button variant="outline" size="lg" onClick={() => navigate("/about")}>
                Learn More
              </Button>
            </div>
          </div>
        </section>

        <section className="container py-12 space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="rounded-xl p-6 glass animate-slide-up" style={{ animationDelay: "300ms" }}>
              <div className="bg-primary/10 rounded-full p-3 w-12 h-12 flex items-center justify-center mb-4">
                <Activity className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-xl font-bold mb-2">Real-time Monitoring</h3>
              <p className="text-muted-foreground">
                Advanced computer vision algorithms to count vehicles and detect traffic patterns in real-time.
              </p>
            </div>

            <div className="rounded-xl p-6 glass animate-slide-up" style={{ animationDelay: "400ms" }}>
              <div className="bg-traffic-emergency/10 rounded-full p-3 w-12 h-12 flex items-center justify-center mb-4">
                <Shield className="h-6 w-6 text-traffic-emergency" />
              </div>
              <h3 className="text-xl font-bold mb-2">Emergency Detection</h3>
              <p className="text-muted-foreground">
                Automatically detects emergency vehicles and provides immediate signal priority.
              </p>
            </div>

            <div className="rounded-xl p-6 glass animate-slide-up" style={{ animationDelay: "500ms" }}>
              <div className="bg-traffic-green/10 rounded-full p-3 w-12 h-12 flex items-center justify-center mb-4">
                <Clock className="h-6 w-6 text-traffic-green" />
              </div>
              <h3 className="text-xl font-bold mb-2">Adaptive Timing</h3>
              <p className="text-muted-foreground">
                Intelligent signal timing adapts to current traffic conditions to reduce congestion.
              </p>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t py-6 md:py-0">
        <div className="container flex flex-col items-center justify-between gap-4 md:h-24 md:flex-row">
          <p className="text-center text-sm leading-loose text-muted-foreground md:text-left">
            © 2023 Smart Traffic Management System. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Index;
