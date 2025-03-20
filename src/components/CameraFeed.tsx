
import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, Camera } from "lucide-react";

interface CameraFeedProps {
  cameraUrl: string;
  title?: string;
  className?: string;
}

const CameraFeed = ({ cameraUrl, title = "Traffic Camera", className }: CameraFeedProps) => {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Handle image loading
  useEffect(() => {
    const timer = setTimeout(() => {
      if (isLoading) {
        setError("Camera feed is taking longer than expected to load. Please check your backend connection.");
      }
    }, 5000);

    return () => clearTimeout(timer);
  }, [isLoading]);

  return (
    <Card className={className}>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg flex items-center gap-2">
          <Camera className="h-5 w-5" />
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0 overflow-hidden rounded-b-xl relative">
        {error ? (
          <div className="bg-destructive/10 text-destructive p-4 flex items-center gap-2">
            <AlertCircle className="h-5 w-5" />
            <p>{error}</p>
          </div>
        ) : (
          <>
            {isLoading && (
              <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
                <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full"></div>
              </div>
            )}
            <img
              src={cameraUrl}
              alt="Traffic Camera Feed"
              className="w-full h-auto"
              onLoad={() => setIsLoading(false)}
              onError={() => {
                setIsLoading(false);
                setError("Failed to load camera feed. Please ensure the backend server is running.");
              }}
            />
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default CameraFeed;
