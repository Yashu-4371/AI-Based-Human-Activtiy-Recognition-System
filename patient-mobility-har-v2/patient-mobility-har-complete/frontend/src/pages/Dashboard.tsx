
import * as React from "react";
import {
  Activity,
  AlertTriangle,
  Users,
  Footprints,
} from "lucide-react";

import { DashboardLayout } from "@/layouts/DashboardLayout";
import { StatCard } from "@/components/dashboard/StatCard";
import { AlertFeed } from "@/components/dashboard/AlertFeed";
import { SystemHealthCard } from "@/components/dashboard/SystemHealthCard";
import { LiveFeed } from "@/components/camera/LiveFeed";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { usePatients } from "@/hooks/usePatients";
import { useWebSocket } from "@/hooks/useWebSocket";

import * as alertService from "@/services/alertService";
import * as cameraService from "@/services/cameraService";

import type { Alert } from "@/services/alertService";
import type { CameraStatus } from "@/services/cameraService";

import { parseServerDate } from "@/lib/utils";

export default function Dashboard() {
  const { patients } = usePatients();
  const { lastMessage, isConnected } = useWebSocket();

  const [alerts, setAlerts] = React.useState<Alert[]>([]);
  const [status, setStatus] =
    React.useState<CameraStatus | null>(null);

  React.useEffect(() => {
    const loadData = async () => {
      try {
        const [alertList, cameraStatus] = await Promise.all([
          alertService.listAlerts({ status: "open" }),
          cameraService.getCameraStatus(),
        ]);

        setAlerts(alertList);
        setStatus(cameraStatus);
      } catch (error) {
        console.error("Dashboard loading error:", error);
      }
    };

    loadData();

    const interval = setInterval(loadData, 10000);

    return () => clearInterval(interval);
  }, []);

  const todaysAlerts = alerts.filter(
    (a) =>
      parseServerDate(a.created_at).toDateString() ===
      new Date().toDateString()
  );

  const criticalCount = alerts.filter(
    (a) => a.priority === "critical"
  ).length;

  return (
    <DashboardLayout title="Dashboard">

      {/* Dashboard Statistics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total Patients"
          value={patients.length}
          icon={Users}
          delay={0}
        />

        <StatCard
          label="Today's Alerts"
          value={todaysAlerts.length}
          icon={AlertTriangle}
          tone="warning"
          delay={0.05}
        />

        <StatCard
          label="Critical Alerts"
          value={criticalCount}
          icon={AlertTriangle}
          tone="destructive"
          delay={0.1}
        />

        <StatCard
          label="Current Activity"
          value={lastMessage?.activity_label ?? "—"}
          icon={Footprints}
          tone="success"
          delay={0.15}
        />
      </div>

      {/* Live Monitoring and System Information */}
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">

        <div className="space-y-6 lg:col-span-2">
          <Card glass>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-primary" />
                Live Monitoring Preview
              </CardTitle>
            </CardHeader>

            <CardContent>
              <LiveFeed
                message={lastMessage}
                isConnected={isConnected}
              />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <SystemHealthCard status={status} />
          <AlertFeed alerts={alerts.slice(0, 6)} />
        </div>

      </div>

    </DashboardLayout>
  );
}
