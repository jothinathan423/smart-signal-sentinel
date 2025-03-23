import React, { useState, useEffect, useRef } from "react";
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
  const [retryCount, setRetryCount] = useState(0);
  const [frameRate, setFrameRate] = useState(1); // 1 fps by default

  // Handle image loading with optimized refresh cycle
  useEffect(() => {
    if (!cameraUrl) return;

    // Set up error timeout
    const errorTimer = setTimeout(() => {
      if (isLoading && retryCount > 2) {
        setError("Camera feed is taking longer than expected to load. Please check your backend connection.");
      }
    }, 5000);

    // Set up periodic refresh to ensure stream keeps flowing
    const refreshTimer = setInterval(() => {
      if (imgRef.current && !isLoading && !error) {
        // Add timestamp to URL to prevent caching
        const timestamp = new Date().getTime();
        const refreshUrl = `${cameraUrl}&t=${timestamp}`;
        imgRef.current.src = refreshUrl;
      }
    }, 1000 / frameRate); // Adjust refresh rate based on frameRate

    return () => {
      clearTimeout(errorTimer);
      clearInterval(refreshTimer);
    };
  }, [cameraUrl, isLoading, error, retryCount, frameRate]);

  const handleRetry = () => {
    setError(null);
    setIsLoading(true);
    setRetryCount(prev => prev + 1);
    
    // Force reload with new timestamp
    if (imgRef.current) {
      const timestamp = new Date().getTime();
      imgRef.current.src = `${cameraUrl}&t=${timestamp}`;
    }
  };

  const handleQualityChange = (newFrameRate: number) => {
    setFrameRate(newFrameRate);
    // No need to update src immediately, the effect will handle it
  };

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
            <div className="absolute top-2 right-2 z-20 bg-black/50 rounded-lg px-2 py-1 text-xs text-white flex items-center gap-2">
              <span>Quality:</span>
              <div className="flex gap-1">
                <button 
                  onClick={() => handleQualityChange(0.5)} 
                  className={`px-2 py-0.5 rounded ${frameRate === 0.5 ? 'bg-primary' : 'bg-gray-700'}`}
                >
                  Low
                </button>
                <button 
                  onClick={() => handleQualityChange(1)} 
                  className={`px-2 py-0.5 rounded ${frameRate === 1 ? 'bg-primary' : 'bg-gray-700'}`}
                >
                  Medium
                </button>
                <button 
                  onClick={() => handleQualityChange(2)} 
                  className={`px-2 py-0.5 rounded ${frameRate === 2 ? 'bg-primary' : 'bg-gray-700'}`}
                >
                  High
                </button>
              </div>
            </div>
            <img
              ref={imgRef}
              src={`${cameraUrl}&t=${Date.now()}`}
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
