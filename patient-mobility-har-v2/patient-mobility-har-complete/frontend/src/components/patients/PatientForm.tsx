import * as React from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Patient, PatientInput } from "@/services/patientService";

interface PatientFormProps {
  initialValues?: Partial<Patient>;
  onSubmit: (values: Partial<PatientInput>) => Promise<void>;
  submitLabel?: string;
}

export function PatientForm({ initialValues, onSubmit, submitLabel = "Save Patient" }: PatientFormProps) {
  const [values, setValues] = React.useState<Partial<PatientInput>>({
    name: initialValues?.name ?? "",
    age: initialValues?.age ?? undefined,
    gender: initialValues?.gender ?? "",
    blood_group: initialValues?.blood_group ?? "",
    disease: initialValues?.disease ?? "",
    doctor: initialValues?.doctor ?? "",
    room_number: initialValues?.room_number ?? "",
    emergency_contact: initialValues?.emergency_contact ?? "",
    medical_notes: initialValues?.medical_notes ?? "",
  });
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const handleChange = (field: keyof PatientInput) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = field === "age" ? (e.target.value ? Number(e.target.value) : undefined) : e.target.value;
    setValues((prev) => ({ ...prev, [field]: value }));
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
        <Label htmlFor="name">Full name</Label>
        <Input id="name" required value={values.name ?? ""} onChange={handleChange("name")} placeholder="Patient name" />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="age">Age</Label>
        <Input id="age" type="number" min={0} value={values.age ?? ""} onChange={handleChange("age")} />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="gender">Gender</Label>
        <Input id="gender" value={values.gender ?? ""} onChange={handleChange("gender")} placeholder="e.g. Female" />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="blood_group">Blood group</Label>
        <Input id="blood_group" value={values.blood_group ?? ""} onChange={handleChange("blood_group")} placeholder="e.g. O+" />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="room_number">Room number</Label>
        <Input id="room_number" value={values.room_number ?? ""} onChange={handleChange("room_number")} />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="disease">Condition / diagnosis</Label>
        <Input id="disease" value={values.disease ?? ""} onChange={handleChange("disease")} />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="doctor">Attending doctor</Label>
        <Input id="doctor" value={values.doctor ?? ""} onChange={handleChange("doctor")} />
      </div>

      <div className="sm:col-span-2 space-y-1.5">
        <Label htmlFor="emergency_contact">Emergency contact</Label>
        <Input id="emergency_contact" value={values.emergency_contact ?? ""} onChange={handleChange("emergency_contact")} />
      </div>

      <div className="sm:col-span-2 space-y-1.5">
        <Label htmlFor="medical_notes">Medical notes</Label>
        <Input id="medical_notes" value={values.medical_notes ?? ""} onChange={handleChange("medical_notes")} />
      </div>

      <div className="sm:col-span-2 flex justify-end">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving..." : submitLabel}
        </Button>
      </div>
    </form>
  );
}
