import * as React from "react";
import { Plus, Search, UserRound } from "lucide-react";
import { DashboardLayout } from "@/layouts/DashboardLayout";
import { PatientCard } from "@/components/patients/PatientCard";
import { PatientForm } from "@/components/patients/PatientForm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { usePatients } from "@/hooks/usePatients";
import { useToast } from "@/components/ui/toast";
import * as patientService from "@/services/patientService";
import type { PatientInput } from "@/services/patientService";

export default function Patients() {
  const { patients, isLoading, refresh } = usePatients();
  const { toast } = useToast();
  const [search, setSearch] = React.useState("");
  const [isDialogOpen, setIsDialogOpen] = React.useState(false);

  const filteredPatients = patients.filter((p) => p.name.toLowerCase().includes(search.toLowerCase()));

  const handleCreate = async (values: Partial<PatientInput>) => {
    await patientService.createPatient(values);
    toast({ title: "Patient added", variant: "success" });
    setIsDialogOpen(false);
    refresh();
  };

  return (
    <DashboardLayout title="Patients">
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-xs">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search patients..."
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" /> Add Patient
            </Button>
          </DialogTrigger>
          <DialogContent className="max-h-[85vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Add New Patient</DialogTitle>
            </DialogHeader>
            <PatientForm onSubmit={handleCreate} submitLabel="Add Patient" />
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading patients...</p>
      ) : filteredPatients.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border py-16 text-center">
          <UserRound className="mb-3 h-10 w-10 text-muted-foreground" />
          <p className="font-medium">No patients found</p>
          <p className="text-sm text-muted-foreground">Add a patient to begin monitoring.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredPatients.map((patient) => (
            <PatientCard key={patient.id} patient={patient} />
          ))}
        </div>
      )}
    </DashboardLayout>
  );
}
