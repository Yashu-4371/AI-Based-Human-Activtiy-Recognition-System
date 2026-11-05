import { Camera, Cpu, Wifi, WifiOff } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { CameraStatus } from "@/services/cameraService";

interface SystemHealthCardProps {
  status: CameraStatus | null;
}

export function SystemHealthCard({ status }: SystemHealthCardProps) {
  const isConnected = status?.camera_connected ?? false;

  return (
    <Card glass>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Cpu className="h-4 w-4 text-primary" />
          System Health
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm">
            <Camera className="h-4 w-4 text-muted-foreground" />
            Camera
          </div>
          <Badge variant={isConnected ? "success" : "destructive"}>
            {isConnected ? "Connected" : "Disconnected"}
          </Badge>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm">
            {isConnected ? (
              <Wifi className="h-4 w-4 text-muted-foreground" />
            ) : (
              <WifiOff className="h-4 w-4 text-muted-foreground" />
            )}
            Monitoring
          </div>
          <Badge variant={status?.is_running ? "success" : "secondary"}>
            {status?.is_running ? "Active" : "Idle"}
          </Badge>
        </div>

        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Frame rate</span>
          <span className="font-mono">{status?.fps?.toFixed(1) ?? "0.0"} FPS</span>
        </div>
      </CardContent>
    </Card>
  );
}
