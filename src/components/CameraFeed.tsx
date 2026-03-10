import React, { useState, useRef, useCallback } from "react";
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
  const imgRef = useRef<HTMLImageElement>(null);
  const [streamKey, setStreamKey] = useState(0);

  // MJPEG streams are continuous - the browser handles frame updates automatically.
  // We should NOT manually refresh/reload the image as that BREAKS the stream
  // and causes the slow rendering issue.

  const handleLoad = useCallback(() => {
    setIsLoading(false);
    setError(null);
  }, []);

  const handleError = useCallback(() => {
    setIsLoading(false);
    setError("Failed to load camera feed. Ensure the backend server is running.");
  }, []);

  const handleRetry = useCallback(() => {
    setError(null);
    setIsLoading(true);
    // Force remount the img element to restart the MJPEG stream
    setStreamKey(prev => prev + 1);
  }, []);

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
          <div className="bg-destructive/10 text-destructive p-4 flex flex-col items-center gap-2">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5" />
              <p>{error}</p>
            </div>
            <button
              onClick={handleRetry}
              className="mt-2 px-3 py-1 bg-primary text-primary-foreground text-sm rounded-md hover:bg-primary/90"
            >
              Retry Connection
            </button>
          </div>
        ) : (
          <>
            {isLoading && (
              <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-10">
                <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full"></div>
              </div>
            )}
            {/*
              MJPEG stream: The browser natively handles multipart/x-mixed-replace.
              Each frame is pushed by the server. No polling or manual refresh needed.
              The key prop forces a fresh connection when retrying.
            */}
            <img
              key={streamKey}
              ref={imgRef}
              src={cameraUrl}
              alt="Traffic Camera Feed"
              className="w-full h-auto"
              onLoad={handleLoad}
              onError={handleError}
            />
          </>
        )}
      </CardContent>
    </Card>
  );
};

export default CameraFeed;
