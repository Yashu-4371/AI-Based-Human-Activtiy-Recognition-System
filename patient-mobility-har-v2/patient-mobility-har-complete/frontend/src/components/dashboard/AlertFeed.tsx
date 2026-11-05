import { AlertTriangle, Clock, CheckCircle2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Alert } from "@/services/alertService";
import { parseServerDate } from "@/lib/utils";

interface AlertFeedProps {
  alerts: Alert[];
  emptyMessage?: string;
}

const priorityVariant: Record<Alert["priority"], "destructive" | "warning" | "secondary"> = {
  critical: "destructive",
  warning: "warning",
  normal: "secondary",
};

export function AlertFeed({ alerts, emptyMessage = "No alerts yet. All quiet." }: AlertFeedProps) {
  return (
    <Card glass>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-warning" />
          Recent Alerts
        </CardTitle>
      </CardHeader>
      <CardContent>
        {alerts.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">{emptyMessage}</p>
        ) : (
          <ul className="space-y-3">
            {alerts.map((alert) => (
              <li key={alert.id} className="flex items-start gap-3 rounded-lg border border-border p-3">
                {alert.status === "resolved" ? (
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                ) : (
                  <Clock className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                )}
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium capitalize">{alert.type} detected</p>
                    <Badge variant={priorityVariant[alert.priority]}>{alert.priority}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">{alert.message}</p>
                  <p className="mt-1 font-mono text-[11px] text-muted-foreground">
                    {parseServerDate(alert.created_at).toLocaleString()}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
