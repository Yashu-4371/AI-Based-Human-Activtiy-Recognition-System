import * as React from "react";
import { Plus, HeartHandshake, Pencil, Trash2, Phone, Mail, Send, AlertTriangle } from "lucide-react";
import { DashboardLayout } from "@/layouts/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { CaregiverForm } from "@/components/caregivers/CaregiverForm";
import { useToast } from "@/components/ui/toast";
import { usePatients } from "@/hooks/usePatients";
import { useAuth } from "@/hooks/useAuth";
import * as caregiverService from "@/services/caregiverService";
import type { Caregiver, CaregiverInput } from "@/services/caregiverService";

export default function Caregivers() {
  const { patients } = usePatients();
  const { toast } = useToast();
  const { user } = useAuth();
  const [sendingTestFor, setSendingTestFor] = React.useState<number | null>(null);
  const [caregivers, setCaregivers] = React.useState<Caregiver[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isCreateOpen, setIsCreateOpen] = React.useState(false);
  const [editingCaregiver, setEditingCaregiver] = React.useState<Caregiver | null>(null);

  const refresh = React.useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await caregiverService.listCaregivers();
      setCaregivers(data);
    } catch {
      toast({ title: "Failed to load caregivers", variant: "destructive" });
    } finally {
      setIsLoading(false);
    }
  }, [toast]);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  const handleCreate = async (values: CaregiverInput) => {
    await caregiverService.createCaregiver(values);
    toast({ title: "Caregiver added", variant: "success" });
    setIsCreateOpen(false);
    refresh();
  };

  const handleUpdate = async (caregiverId: number, values: CaregiverInput) => {
    const original = caregivers.find((c) => c.id === caregiverId);
    const originalPatientIds = new Set(original?.patients.map((p) => p.id) ?? []);
    const nextPatientIds = new Set(values.patient_ids ?? []);

    await caregiverService.updateCaregiver(caregiverId, {
      full_name: values.full_name,
      phone: values.phone,
      email: values.email,
      relationship_to_patient: values.relationship_to_patient,
      additional_contact_info: values.additional_contact_info,
    });

    // Assignment is managed via separate assign/unassign endpoints on the backend.
    for (const id of nextPatientIds) {
      if (!originalPatientIds.has(id)) await caregiverService.assignCaregiver(caregiverId, id);
    }
    for (const id of originalPatientIds) {
      if (!nextPatientIds.has(id)) await caregiverService.unassignCaregiver(caregiverId, id);
    }

    toast({ title: "Caregiver updated", variant: "success" });
    setEditingCaregiver(null);
    refresh();
  };

  const handleDelete = async (caregiver: Caregiver) => {
    if (!confirm(`Remove caregiver ${caregiver.full_name}?`)) return;
    await caregiverService.deleteCaregiver(caregiver.id);
    toast({ title: "Caregiver removed" });
    refresh();
  };

  const handleTestEmail = async (caregiver: Caregiver) => {
    setSendingTestFor(caregiver.id);
    try {
      const result = await caregiverService.sendTestEmail(caregiver.id);
      toast({ title: "Test email sent", description: result.message, variant: "success" });
    } catch (error) {
      const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast({ title: "Test email failed", description: detail ?? "Could not reach the server.", variant: "destructive" });
    } finally {
      setSendingTestFor(null);
    }
  };

  return (
    <DashboardLayout title="Caregivers">
      <div className="mb-6 flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          When a fall or prolonged inactivity is detected, an email is sent automatically to the email address saved for each caregiver assigned to that patient (plus SMS/WhatsApp/call if configured). A caregiver must be assigned to a patient to receive that patient's alerts.
        </p>
        <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" /> Add Caregiver
            </Button>
          </DialogTrigger>
          <DialogContent className="max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Add Caregiver</DialogTitle>
            </DialogHeader>
            <CaregiverForm patients={patients} onSubmit={handleCreate} submitLabel="Add Caregiver" />
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading caregivers...</p>
      ) : caregivers.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border py-16 text-center">
          <HeartHandshake className="mb-3 h-10 w-10 text-muted-foreground" />
          <p className="font-medium">No caregivers yet</p>
          <p className="text-sm text-muted-foreground">Add a caregiver and assign them to a patient to enable alert notifications.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {caregivers.map((caregiver) => (
            <Card key={caregiver.id}>
              <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
                <div>
                  <CardTitle className="text-base">{caregiver.full_name}</CardTitle>
                  {caregiver.relationship_to_patient && (
                    <p className="text-xs text-muted-foreground">{caregiver.relationship_to_patient}</p>
                  )}
                </div>
                <div className="flex gap-1">
                  {user?.role === "admin" && caregiver.email && (
                    <Button
                      size="icon"
                      variant="ghost"
                      title="Send a test email to this caregiver"
                      disabled={sendingTestFor === caregiver.id}
                      onClick={() => handleTestEmail(caregiver)}
                    >
                      <Send className="h-4 w-4" />
                    </Button>
                  )}
                  <Button size="icon" variant="ghost" onClick={() => setEditingCaregiver(caregiver)}>
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button size="icon" variant="ghost" onClick={() => handleDelete(caregiver)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                <p className="flex items-center gap-2 text-muted-foreground">
                  <Phone className="h-3.5 w-3.5" /> {caregiver.phone}
                </p>
                {caregiver.email && (
                  <p className="flex items-center gap-2 text-muted-foreground">
                    <Mail className="h-3.5 w-3.5" /> {caregiver.email}
                  </p>
                )}
                {!caregiver.email && (
                  <p className="flex items-center gap-2 text-xs text-warning">
                    <AlertTriangle className="h-3.5 w-3.5" /> No email saved — this caregiver cannot receive email alerts.
                  </p>
                )}
                {caregiver.email && caregiver.patients.length === 0 && (
                  <p className="flex items-center gap-2 text-xs text-warning">
                    <AlertTriangle className="h-3.5 w-3.5" /> Not assigned to a patient yet — no alerts will be emailed.
                  </p>
                )}
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {caregiver.patients.length === 0 ? (
                    <Badge variant="outline">Unassigned</Badge>
                  ) : (
                    caregiver.patients.map((p) => (
                      <Badge key={p.id} variant="secondary">
                        {p.name}
                      </Badge>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={!!editingCaregiver} onOpenChange={(open) => !open && setEditingCaregiver(null)}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Caregiver</DialogTitle>
          </DialogHeader>
          {editingCaregiver && (
            <CaregiverForm
              patients={patients}
              initialValues={editingCaregiver}
              onSubmit={(values) => handleUpdate(editingCaregiver.id, values)}
              submitLabel="Save Changes"
            />
          )}
        </DialogContent>
      </Dialog>
    </DashboardLayout>
  );
}
