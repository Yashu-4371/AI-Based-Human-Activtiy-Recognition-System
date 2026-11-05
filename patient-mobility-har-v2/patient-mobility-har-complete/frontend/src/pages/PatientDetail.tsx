import * as React from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Trash2, FileDown, Footprints, User, Armchair, BedDouble } from "lucide-react";
import { DashboardLayout } from "@/layouts/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { PatientForm } from "@/components/patients/PatientForm";
import { useToast } from "@/components/ui/toast";
import * as patientService from "@/services/patientService";
import * as alertService from "@/services/alertService";
import * as reportService from "@/services/reportService";
import { api } from "@/services/api";
import type { Patient, PatientInput } from "@/services/patientService";
import type { Alert as AlertRecord } from "@/services/alertService";
import { parseServerDate } from "@/lib/utils";

interface ActivityRecord {
  id: number;
  activity_type: string;
  confidence: number;
  started_at: string;
  ended_at: string | null;
  duration_sec: number | null;
}

const activityIcons: Record<string, React.ElementType> = {
  walking: Footprints,
  standing: User,
  sitting: Armchair,
  lying: BedDouble,
};

export default function PatientDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [patient, setPatient] = React.useState<Patient | null>(null);
  const [activities, setActivities] = React.useState<ActivityRecord[]>([]);
  const [alerts, setAlerts] = React.useState<AlertRecord[]>([]);
  const [isEditOpen, setIsEditOpen] = React.useState(false);

  const loadAll = React.useCallback(async () => {
    if (!id) return;
    const patientId = Number(id);
    const [patientData, historyResponse, alertList] = await Promise.all([
      patientService.getPatient(patientId),
      api.get<ActivityRecord[]>("/activities/history", { params: { patient_id: patientId } }),
      alertService.listAlerts({ patient_id: patientId }),
    ]);
    setPatient(patientData);
    setActivities(historyResponse.data);
    setAlerts(alertList);
  }, [id]);

  React.useEffect(() => {
    loadAll();
  }, [loadAll]);

  const handleUpdate = async (values: Partial<PatientInput>) => {
    if (!patient) return;
    await patientService.updatePatient(patient.id, values);
    toast({ title: "Patient updated", variant: "success" });
    setIsEditOpen(false);
    loadAll();
  };

  const handleDelete = async () => {
    if (!patient) return;
    if (!window.confirm(`Remove ${patient.name} from the system? This cannot be undone.`)) return;
    await patientService.deletePatient(patient.id);
    toast({ title: "Patient removed" });
    navigate("/patients");
  };

  const handleGenerateReport = async (type: "daily" | "weekly" | "monthly") => {
    if (!patient) return;
    const report = await reportService.generateReport(patient.id, type, "pdf");
    toast({ title: `${type} report generated`, variant: "success" });
    try {
      await reportService.downloadReport(report.id);
    } catch {
      toast({ title: "Download failed", description: "The report was generated but couldn't be downloaded.", variant: "destructive" });
    }
  };

  if (!patient) {
    return (
      <DashboardLayout title="Patient Detail">
        <p className="text-sm text-muted-foreground">Loading patient...</p>
      </DashboardLayout>
    );
  }

  const initials = patient.name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase();

  return (
    <DashboardLayout title={patient.name}>
      <Button variant="ghost" size="sm" onClick={() => navigate("/patients")} className="mb-4">
        <ArrowLeft className="mr-2 h-4 w-4" /> Back to Patients
      </Button>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card glass className="lg:col-span-1 h-fit">
          <CardContent className="p-6 text-center">
            <Avatar className="mx-auto h-20 w-20">
              {patient.photo_path && <AvatarImage src={patient.photo_path} alt={patient.name} />}
              <AvatarFallback className="text-xl">{initials}</AvatarFallback>
            </Avatar>
            <h2 className="mt-4 font-display text-lg font-bold">{patient.name}</h2>
            <p className="text-sm text-muted-foreground">
              {patient.age ? `${patient.age} yrs` : "Age N/A"} · {patient.gender ?? "N/A"}
            </p>

            <div className="mt-4 space-y-2 text-left text-sm">
              <DetailRow label="Room" value={patient.room_number} />
              <DetailRow label="Blood Group" value={patient.blood_group} />
              <DetailRow label="Condition" value={patient.disease} />
              <DetailRow label="Doctor" value={patient.doctor} />
              <DetailRow label="Emergency Contact" value={patient.emergency_contact} />
              <DetailRow label="Notes" value={patient.medical_notes} />
            </div>

            <div className="mt-6 flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => setIsEditOpen(true)}>
                Edit
              </Button>
              <Button variant="destructive" size="icon" onClick={handleDelete}>
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="lg:col-span-2 space-y-6">
          <Card glass>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle>Generate Report</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {(["daily", "weekly", "monthly"] as const).map((type) => (
                <Button key={type} variant="secondary" size="sm" onClick={() => handleGenerateReport(type)}>
                  <FileDown className="mr-2 h-3.5 w-3.5" />
                  <span className="capitalize">{type}</span>
                </Button>
              ))}
            </CardContent>
          </Card>

          <Card glass>
            <CardHeader>
              <CardTitle>Activity Timeline & Alerts</CardTitle>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="activity">
                <TabsList>
                  <TabsTrigger value="activity">Activity</TabsTrigger>
                  <TabsTrigger value="alerts">Alerts</TabsTrigger>
                </TabsList>

                <TabsContent value="activity">
                  {activities.length === 0 ? (
                    <p className="py-6 text-center text-sm text-muted-foreground">No activity recorded yet.</p>
                  ) : (
                    <ul className="space-y-2">
                      {activities.map((a) => {
                        const Icon = activityIcons[a.activity_type] ?? User;
                        return (
                          <li key={a.id} className="flex items-center gap-3 rounded-lg border border-border p-3">
                            <Icon className="h-4 w-4 text-primary" />
                            <div className="flex-1">
                              <p className="text-sm font-medium capitalize">{a.activity_type}</p>
                              <p className="font-mono text-xs text-muted-foreground">
                                {parseServerDate(a.started_at).toLocaleString()}
                                {a.duration_sec ? ` · ${Math.round(a.duration_sec)}s` : ""}
                              </p>
                            </div>
                            <Badge variant="outline">{(a.confidence * 100).toFixed(0)}%</Badge>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </TabsContent>

                <TabsContent value="alerts">
                  {alerts.length === 0 ? (
                    <p className="py-6 text-center text-sm text-muted-foreground">No alerts for this patient.</p>
                  ) : (
                    <ul className="space-y-2">
                      {alerts.map((alert) => (
                        <li key={alert.id} className="flex items-center gap-3 rounded-lg border border-border p-3">
                          <div className="flex-1">
                            <p className="text-sm font-medium capitalize">{alert.type}</p>
                            <p className="text-xs text-muted-foreground">{alert.message}</p>
                          </div>
                          <Badge variant={alert.priority === "critical" ? "destructive" : "warning"}>
                            {alert.priority}
                          </Badge>
                        </li>
                      ))}
                    </ul>
                  )}
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </div>
      </div>

      <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Patient</DialogTitle>
          </DialogHeader>
          <PatientForm initialValues={patient} onSubmit={handleUpdate} submitLabel="Update Patient" />
        </DialogContent>
      </Dialog>
    </DashboardLayout>
  );
}

function DetailRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex justify-between border-b border-border/60 py-1.5">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value || "—"}</span>
    </div>
  );
}
