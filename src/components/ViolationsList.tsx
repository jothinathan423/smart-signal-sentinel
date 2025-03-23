
import { useState } from "react";
import { ViolationData } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { 
  AlertTriangle, 
  Car, 
  Clock, 
  MapPin,
  Search,
  Info
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

interface ViolationsListProps {
  violations: ViolationData[];
  isLoading: boolean;
}

const ViolationsList = ({ violations, isLoading }: ViolationsListProps) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [expandedViolation, setExpandedViolation] = useState<string | null>(null);
  
  // Add console logs to debug
  console.log("ViolationsList received:", { violations, isLoading });
  
  // Filter violations based on search term - safely handle undefined
  const filteredViolations = Array.isArray(violations) ? violations.filter((violation) => 
    violation?.vehicleNumber?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    violation?.type?.toLowerCase().includes(searchTerm.toLowerCase())
  ) : [];

  const getViolationTypeLabel = (type: string) => {
    switch (type) {
      case "red_light":
        return "Red Light Violation";
      case "speeding":
        return "Speeding";
      case "no_helmet":
        return "No Helmet";
      case "excess_passengers":
        return "Excess Passengers";
      case "other":
        return "Other Violation";
      default:
        return type;
    }
  };

  const getViolationColor = (type: string) => {
    switch (type) {
      case "red_light":
        return "destructive";
      case "speeding":
        return "yellow";
      case "no_helmet":
        return "orange";
      case "excess_passengers":
        return "purple";
      case "other":
        return "default";
      default:
        return "default";
    }
  };

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-lg flex items-center gap-2">
          <AlertTriangle className="h-5 w-5 text-destructive" />
          Traffic Violations
        </CardTitle>
        <div className="relative">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by vehicle number or type..."
            className="pl-8"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </CardHeader>
      <CardContent className="px-2">
        {isLoading ? (
          <div className="flex items-center justify-center p-4">
            <div className="animate-spin h-6 w-6 border-4 border-primary border-t-transparent rounded-full"></div>
          </div>
        ) : !Array.isArray(violations) ? (
          <div className="text-center py-6 text-muted-foreground">
            Error loading violations data
          </div>
        ) : violations.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            {searchTerm ? "No matching violations found" : "No violations recorded yet"}
          </div>
        ) : (
          <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2">
            {filteredViolations.map((violation) => (
              <div
                key={violation.id}
                className="bg-muted/30 rounded-lg p-3 hover:bg-muted/50 transition-colors"
              >
                <div className="flex justify-between items-start mb-2">
                  <div className="flex items-center gap-2">
                    <Car className="h-4 w-4" />
                    <span className="font-mono font-semibold">{violation.vehicleNumber}</span>
                  </div>
                  <Badge variant={getViolationColor(violation.type) as any}>
                    {getViolationTypeLabel(violation.type)}
                  </Badge>
                </div>
                
                <div className="flex flex-col gap-1 text-sm">
                  <div className="flex items-center gap-2">
                    <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                    <span>{new Date(violation.timestamp).toLocaleString()}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <MapPin className="h-3.5 w-3.5 text-muted-foreground" />
                    <span>{violation.location}</span>
                  </div>
                  
                  {violation.details && (
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      className="w-full mt-1 justify-start text-xs gap-1 h-auto py-1"
                      onClick={() => setExpandedViolation(expandedViolation === violation.id ? null : violation.id)}
                    >
                      <Info className="h-3.5 w-3.5" />
                      {expandedViolation === violation.id ? "Hide details" : "Show details"}
                    </Button>
                  )}
                  
                  {expandedViolation === violation.id && violation.details && (
                    <div className="bg-background/50 rounded p-2 mt-1 text-xs">
                      {violation.details}
                      {violation.imageUrl && (
                        <img 
                          src={violation.imageUrl} 
                          alt="Violation evidence" 
                          className="w-full h-auto mt-2 rounded border border-border"
                        />
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ViolationsList;
