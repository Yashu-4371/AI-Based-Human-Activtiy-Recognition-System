import * as React from "react";
import { Play, Square } from "lucide-react";
import { DashboardLayout } from "@/layouts/DashboardLayout";
import { LiveFeed } from "@/components/camera/LiveFeed";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useWebSocket } from "@/hooks/useWebSocket";
import { usePatients } from "@/hooks/usePatients";
import { useToast } from "@/components/ui/toast";
import * as cameraService from "@/services/cameraService";
import type { CameraSetting, CameraStatus } from "@/services/cameraService";

export default function LiveMonitor() {
  const { lastMessage, isConnected } = useWebSocket();
  const { patients } = usePatients();
  const { toast } = useToast();

  const [cameras, setCameras] = React.useState<CameraSetting[]>([]);
  const [selectedPatientId, setSelectedPatientId] = React.useState<string>("");
  const [selectedCameraId, setSelectedCameraId] = React.useState<string>("");
  const [status, setStatus] = React.useState<CameraStatus | null>(null);
  const [isBusy, setIsBusy] = React.useState(false);
  const prevFallRef = React.useRef(false);
  const prevInactivityRef = React.useRef(false);

  // Immediate in-app notification: fire a toast the instant the live
  // pipeline flags a new fall/inactivity event, rather than waiting for
  // the Alerts page to be opened/refreshed. Edge-triggered (only on the
  // false -> true transition) so it doesn't re-toast every websocket
  // frame while the condition remains active.
  React.useEffect(() => {
    if (!lastMessage) return;

    if (lastMessage.fall_detected && !prevFallRef.current) {
      toast({ title: "Fall detected!", description: "A fall was just confirmed for this patient.", variant: "destructive" });
    }
    prevFallRef.current = lastMessage.fall_detected;

    if (lastMessage.inactivity_warning && !prevInactivityRef.current) {
      toast({ title: "Prolonged inactivity detected", variant: "warning" });
    }
    prevInactivityRef.current = lastMessage.inactivity_warning;
  }, [lastMessage, toast]);

  const refreshStatus = React.useCallback(async () => {
    const data = await cameraService.getCameraStatus();
    setStatus(data);
  }, []);

  React.useEffect(() => {
    cameraService.listCameraSettings().then(setCameras);
    refreshStatus();
    const interval = setInterval(refreshStatus, 5000);
    return () => clearInterval(interval);
  }, [refreshStatus]);

  const handleStart = async () => {
    if (!selectedPatientId || !selectedCameraId) {
      toast({ title: "Select a patient and camera first", variant: "warning" });
      return;
    }
    setIsBusy(true);
    try {
      await cameraService.startCamera(Number(selectedPatientId), Number(selectedCameraId));
      toast({ title: "Monitoring started", variant: "success" });
      await refreshStatus();
    } catch {
      toast({ title: "Failed to start monitoring", variant: "destructive" });
    } finally {
      setIsBusy(false);
    }
  };

  const handleStop = async () => {
    setIsBusy(true);
    try {
      await cameraService.stopCamera();
      toast({ title: "Monitoring stopped" });
      await refreshStatus();
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <DashboardLayout title="Live Monitor">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card glass>
            <CardContent className="p-4">
              <LiveFeed message={lastMessage} isConnected={isConnected} />
            </CardContent>
          </Card>
        </div>

        <Card glass className="h-fit">
          <CardHeader>
            <CardTitle>Monitoring Controls</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Patient</label>
              <Select value={selectedPatientId} onValueChange={setSelectedPatientId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a patient" />
                </SelectTrigger>
                <SelectContent>
                  {patients.map((p) => (
                    <SelectItem key={p.id} value={String(p.id)}>
                      {p.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium">Camera</label>
              <Select value={selectedCameraId} onValueChange={setSelectedCameraId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a camera" />
                </SelectTrigger>
                <SelectContent>
                  {cameras.map((c) => (
                    <SelectItem key={c.id} value={String(c.id)}>
                      {c.name} ({c.source_type})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex gap-2 pt-2">
              {status?.is_running ? (
                <Button variant="destructive" className="w-full" onClick={handleStop} disabled={isBusy}>
                  <Square className="mr-2 h-4 w-4" /> Stop Monitoring
                </Button>
              ) : (
                <Button className="w-full" onClick={handleStart} disabled={isBusy}>
                  <Play className="mr-2 h-4 w-4" /> Start Monitoring
                </Button>
              )}
            </div>

            <div className="rounded-lg border border-border p-3 text-sm text-muted-foreground">
              <p>Status: <span className="font-medium text-foreground">{status?.is_running ? "Running" : "Idle"}</span></p>
              <p>FPS: <span className="font-mono text-foreground">{status?.fps?.toFixed(1) ?? "0.0"}</span></p>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
