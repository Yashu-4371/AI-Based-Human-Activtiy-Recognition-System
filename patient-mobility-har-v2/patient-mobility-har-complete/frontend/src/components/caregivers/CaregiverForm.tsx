import * as React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Caregiver, CaregiverInput } from "@/services/caregiverService";
import type { Patient } from "@/services/patientService";

interface CaregiverFormProps {
  initialValues?: Caregiver;
  patients: Patient[];
  onSubmit: (values: CaregiverInput) => Promise<void>;
  submitLabel?: string;
}

export function CaregiverForm({ initialValues, patients, onSubmit, submitLabel = "Save Caregiver" }: CaregiverFormProps) {
  const [values, setValues] = React.useState<CaregiverInput>({
    full_name: initialValues?.full_name ?? "",
    phone: initialValues?.phone ?? "",
    email: initialValues?.email ?? "",
    relationship_to_patient: initialValues?.relationship_to_patient ?? "",
    additional_contact_info: initialValues?.additional_contact_info ?? "",
    patient_ids: initialValues?.patients.map((p) => p.id) ?? [],
  });
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const handleChange = (field: keyof CaregiverInput) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setValues((prev) => ({ ...prev, [field]: e.target.value }));
  };

  const togglePatient = (patientId: number) => {
    setValues((prev) => {
      const current = prev.patient_ids ?? [];
      const next = current.includes(patientId) ? current.filter((id) => id !== patientId) : [...current, patientId];
      return { ...prev, patient_ids: next };
    });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await onSubmit(values);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <div className="sm:col-span-2 space-y-1.5">
        <Label htmlFor="full_name">Full name</Label>
        <Input id="full_name" required value={values.full_name} onChange={handleChange("full_name")} placeholder="Caregiver name" />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="phone">Phone</Label>
        <Input id="phone" required value={values.phone} onChange={handleChange("phone")} placeholder="+1 555 000 0000" />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="email">Email</Label>
        <Input id="email" type="email" value={values.email} onChange={handleChange("email")} placeholder="name@gmail.com" />
        <p className="text-xs text-muted-foreground">Alert emails for the assigned patients are sent here.</p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="relationship_to_patient">Relationship</Label>
        <Input
          id="relationship_to_patient"
          value={values.relationship_to_patient}
          onChange={handleChange("relationship_to_patient")}
          placeholder="e.g. Daughter, Home nurse"
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="additional_contact_info">Additional contact info</Label>
        <Input
          id="additional_contact_info"
          value={values.additional_contact_info}
          onChange={handleChange("additional_contact_info")}
          placeholder="Optional"
        />
      </div>

      <div className="sm:col-span-2 space-y-1.5">
        <Label>Assigned patients (alerts for these patients go to this caregiver)</Label>
        {patients.length === 0 ? (
          <p className="text-sm text-muted-foreground">No patients yet — add a patient first.</p>
        ) : (
          <div className="max-h-40 overflow-y-auto rounded-lg border border-border p-2 space-y-1">
            {patients.map((patient) => (
              <label key={patient.id} className="flex items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-secondary">
                <input
                  type="checkbox"
                  checked={(values.patient_ids ?? []).includes(patient.id)}
                  onChange={() => togglePatient(patient.id)}
                  className="h-4 w-4 rounded border-input"
                />
                {patient.name}
              </label>
            ))}
          </div>
        )}
      </div>

      <div className="sm:col-span-2 flex justify-end">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving..." : submitLabel}
        </Button>
      </div>
    </form>
  );
}
