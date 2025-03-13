
import React from "react";
import Navigation from "@/components/Navigation";
import { Separator } from "@/components/ui/separator";

const About = () => {
  return (
    <div className="min-h-screen flex flex-col">
      <Navigation />
      
      <main className="flex-1 container py-6">
        <div className="max-w-3xl mx-auto space-y-8 animate-fade-in">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">About the Project</h1>
            <p className="text-muted-foreground mt-2">
              Smart Traffic Management System with Emergency Vehicle Detection
            </p>
          </div>
          
          <Separator />
          
          <div className="space-y-4">
            <h2 className="text-2xl font-semibold">Overview</h2>
            <p>
              The Smart Traffic Management System is an advanced solution designed to monitor traffic flow at intersections and
              provide intelligent traffic signal control. The system utilizes computer vision technology to count vehicles,
              detect emergency vehicles like ambulances, and automatically adjust traffic signals to optimize traffic flow
              and prioritize emergency response.
            </p>
          </div>
          
          <div className="space-y-4">
            <h2 className="text-2xl font-semibold">Technical Details</h2>
            <div className="space-y-2">
              <h3 className="text-xl font-medium">Frontend</h3>
              <p>
                The frontend is built with React and TypeScript, providing a responsive and interactive user interface.
                Real-time traffic data is visualized using modern UI components and data visualization charts.
              </p>
            </div>
            <div className="space-y-2 mt-4">
              <h3 className="text-xl font-medium">Backend</h3>
              <p>
                The Python backend uses computer vision algorithms to process video feeds from traffic cameras.
                Key technologies include:
              </p>
              <ul className="list-disc list-inside space-y-1 pl-4">
                <li>OpenCV for image processing and video analysis</li>
                <li>YOLOv4 for object detection (vehicles and emergency vehicles)</li>
                <li>Flask for the REST API endpoints</li>
                <li>Real-time WebSocket communication for live updates</li>
              </ul>
            </div>
          </div>
          
          <div className="space-y-4">
            <h2 className="text-2xl font-semibold">Key Features</h2>
            <ul className="list-disc list-inside space-y-3 pl-4">
              <li>
                <span className="font-medium">Real-time Vehicle Detection and Counting:</span>
                <p className="ml-6 mt-1">
                  Advanced computer vision algorithms identify and count vehicles at intersections, providing accurate
                  traffic density information.
                </p>
              </li>
              <li>
                <span className="font-medium">Emergency Vehicle Detection:</span>
                <p className="ml-6 mt-1">
                  The system can recognize emergency vehicles through visual patterns (lights, markings) and sound
                  detection (sirens).
                </p>
              </li>
              <li>
                <span className="font-medium">Automated Signal Control:</span>
                <p className="ml-6 mt-1">
                  Traffic signals automatically adjust based on traffic density and the presence of emergency vehicles,
                  turning green to allow emergency vehicles to pass quickly.
                </p>
              </li>
              <li>
                <span className="font-medium">Data Visualization:</span>
                <p className="ml-6 mt-1">
                  The dashboard presents real-time and historical traffic data in an intuitive format for operators
                  and traffic management personnel.
                </p>
              </li>
            </ul>
          </div>
          
          <div className="space-y-4">
            <h2 className="text-2xl font-semibold">How It Works</h2>
            <ol className="list-decimal list-inside space-y-3 pl-4">
              <li>
                <span className="font-medium">Video Feed Processing:</span>
                <p className="ml-6 mt-1">
                  Cameras at intersections capture video feeds that are processed by the system.
                </p>
              </li>
              <li>
                <span className="font-medium">Vehicle Detection:</span>
                <p className="ml-6 mt-1">
                  Computer vision algorithms detect and count vehicles at the intersection.
                </p>
              </li>
              <li>
                <span className="font-medium">Emergency Vehicle Recognition:</span>
                <p className="ml-6 mt-1">
                  The system analyzes vehicle characteristics to identify emergency vehicles like ambulances.
                </p>
              </li>
              <li>
                <span className="font-medium">Signal Control:</span>
                <p className="ml-6 mt-1">
                  Based on traffic conditions and emergency vehicle presence, the system controls traffic signals.
                </p>
              </li>
              <li>
                <span className="font-medium">Dashboard Updates:</span>
                <p className="ml-6 mt-1">
                  All data is sent to the dashboard for visualization and monitoring.
                </p>
              </li>
            </ol>
          </div>
        </div>
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

export default About;
