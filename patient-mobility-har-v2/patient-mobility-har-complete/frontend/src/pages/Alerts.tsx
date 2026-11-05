import * as React from "react";
import { CheckCircle2, AlertOctagon, Clock3, Image as ImageIcon, Mail } from "lucide-react";
import { DashboardLayout } from "@/layouts/DashboardLayout";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import * as alertService from "@/services/alertService";
import type { Alert, AlertPriority, AlertStatus } from "@/services/alertService";
import { parseServerDate } from "@/lib/utils";

const priorityVariant: Record<AlertPriority, "destructive" | "warning" | "secondary"> = {
  critical: "destructive",
  warning: "warning",
  normal: "secondary",
};

/** One short line + tooltip describing whether caregivers were e-mailed about this alert. */
function emailSummary(alert: Alert): { label: string; variant: "success" | "destructive" | "warning" | "outline"; title: string } | null {
  const rows = alert.email_deliveries ?? [];
  if (rows.length === 0) return null;
  const sent = rows.filter((r) => r.status === "sent").length;
  const failed = rows.filter((r) => r.status === "failed");
  const pending = rows.filter((r) => r.status === "pending").length;
  const skipped = rows.filter((r) => r.status === "skipped");
  const title = rows.map((r) => `${r.status}${r.detail ? `: ${r.detail}` : ""}`).join("\n");
  if (failed.length > 0) return { label: sent > 0 ? `Email: ${sent} sent, ${failed.length} failed` : "Email failed", variant: "destructive", title };
  if (pending > 0) return { label: "Email sending…", variant: "outline", title };
  if (sent > 0) return { label: `Email sent to ${sent} caregiver${sent === 1 ? "" : "s"}`, variant: "success", title };
  return { label: "Email not sent", variant: "warning", title: skipped.map((r) => r.detail).filter(Boolean).join("\n") || title };
}

export default function Alerts() {
  const [alerts, setAlerts] = React.useState<Alert[]>([]);
  const [statusFilter, setStatusFilter] = React.useState<string>("all");
  const [priorityFilter, setPriorityFilter] = React.useState<string>("all");
  const { toast } = useToast();

  const load = React.useCallback(async () => {
    const data = await alertService.listAlerts({
      status: statusFilter === "all" ? undefined : (statusFilter as AlertStatus),
      priority: priorityFilter === "all" ? undefined : (priorityFilter as AlertPriority),
    });
    setAlerts(data);
  }, [statusFilter, priorityFilter]);

  React.useEffect(() => {
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, [load]);

  const handleResolve = async (id: number) => {
    await alertService.resolveAlert(id);
    toast({ title: "Alert resolved", variant: "success" });
    load();
  };

  return (
    <DashboardLayout title="Alerts">
      <div className="mb-6 flex flex-wrap gap-3">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="open">Open</SelectItem>
            <SelectItem value="resolved">Resolved</SelectItem>
          </SelectContent>
        </Select>

        <Select value={priorityFilter} onValueChange={setPriorityFilter}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Priority" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All priorities</SelectItem>
            <SelectItem value="critical">Critical</SelectItem>
            <SelectItem value="warning">Warning</SelectItem>
            <SelectItem value="normal">Normal</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {alerts.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border py-16 text-center">
          <CheckCircle2 className="mb-3 h-10 w-10 text-success" />
          <p className="font-medium">No alerts match this filter</p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => (
            <Card key={alert.id} glass>
              <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-3">
                  {alert.type === "fall" ? (
                    <AlertOctagon className="mt-0.5 h-5 w-5 text-destructive" />
                  ) : (
                    <Clock3 className="mt-0.5 h-5 w-5 text-warning" />
                  )}
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium capitalize">{alert.type} — Patient #{alert.patient_id}</p>
                      <Badge variant={priorityVariant[alert.priority]}>{alert.priority}</Badge>
                      <Badge variant={alert.status === "resolved" ? "success" : "outline"}>{alert.status}</Badge>
                      {(() => {
                        const summary = emailSummary(alert);
                        return summary ? (
                          <span title={summary.title}>
                            <Badge variant={summary.variant}>
                              <Mail className="mr-1 h-3 w-3" /> {summary.label}
                            </Badge>
                          </span>
                        ) : null;
                      })()}
                    </div>
                    <p className="text-sm text-muted-foreground">{alert.message}</p>
                    <p className="font-mono text-xs text-muted-foreground">{parseServerDate(alert.created_at).toLocaleString()}</p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {alert.screenshot_path && (
                    <a href={alert.screenshot_path} target="_blank" rel="noreferrer">
                      <Button variant="outline" size="sm">
                        <ImageIcon className="mr-1.5 h-3.5 w-3.5" /> Screenshot
                      </Button>
                    </a>
                  )}
                  {alert.status === "open" && (
                    <Button size="sm" onClick={() => handleResolve(alert.id)}>
                      Resolve
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </DashboardLayout>
  );
}
