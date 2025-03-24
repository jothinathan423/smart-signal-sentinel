
import { useState, useEffect } from "react";
import { ViolationData } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { 
  AlertTriangle, 
  Car, 
  Clock, 
  MapPin,
  Search,
  Info,
  Filter
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface ViolationsListProps {
  violations: ViolationData[];
  isLoading: boolean;
}

const ViolationsList = ({ violations, isLoading }: ViolationsListProps) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [expandedViolation, setExpandedViolation] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string>("all");
  
  // Add console logs to debug
  console.log("ViolationsList received:", { violations, isLoading, violationsLength: violations?.length });
  
  // Filter violations based on search term and type filter - safely handle undefined
  const filteredViolations = Array.isArray(violations) ? violations.filter((violation) => {
    // First check if the violation exists and has required properties
    if (!violation || !violation.vehicleNumber || !violation.type) {
      console.log("Invalid violation data:", violation);
      return false;
    }
    
    // Apply search filter
    const matchesSearch = 
      violation.vehicleNumber.toLowerCase().includes(searchTerm.toLowerCase()) ||
      violation.type.toLowerCase().includes(searchTerm.toLowerCase());
    
    // Apply type filter
    const matchesType = filterType === "all" || violation.type === filterType;
    
    return matchesSearch && matchesType;
  }) : [];
  
  console.log("Filtered violations:", filteredViolations.length);

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
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search by vehicle number or type..."
              className="pl-8"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <Select value={filterType} onValueChange={setFilterType}>
            <SelectTrigger className="w-full sm:w-[180px]">
              <div className="flex items-center">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue placeholder="Filter by type" />
              </div>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Violations</SelectItem>
              <SelectItem value="red_light">Red Light</SelectItem>
              <SelectItem value="speeding">Speeding</SelectItem>
              <SelectItem value="no_helmet">No Helmet</SelectItem>
              <SelectItem value="excess_passengers">Excess Passengers</SelectItem>
              <SelectItem value="other">Other</SelectItem>
            </SelectContent>
          </Select>
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
        ) : filteredViolations.length === 0 ? (
          <div className="text-center py-6 text-muted-foreground">
            No violations match your search criteria
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
                          onError={(e) => {
                            // Handle broken image URLs
                            const target = e.target as HTMLImageElement;
                            target.style.display = 'none';
                          }}
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
