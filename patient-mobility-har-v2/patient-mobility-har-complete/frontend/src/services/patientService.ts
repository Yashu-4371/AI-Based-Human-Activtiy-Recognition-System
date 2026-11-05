import { api } from "./api";

export interface Patient {
  id: number;
  name: string;
  photo_path: string | null;
  age: number | null;
  gender: string | null;
  blood_group: string | null;
  disease: string | null;
  doctor: string | null;
  room_number: string | null;
  emergency_contact: string | null;
  medical_notes: string | null;
  created_at: string;
}

export type PatientInput = Omit<Patient, "id" | "photo_path" | "created_at">;

export async function listPatients(): Promise<Patient[]> {
  const { data } = await api.get<Patient[]>("/patients");
  return data;
}

export async function getPatient(id: number): Promise<Patient> {
  const { data } = await api.get<Patient>(`/patients/${id}`);
  return data;
}

export async function createPatient(input: Partial<PatientInput>): Promise<Patient> {
  const { data } = await api.post<Patient>("/patients", input);
  return data;
}

export async function updatePatient(id: number, input: Partial<PatientInput>): Promise<Patient> {
  const { data } = await api.put<Patient>(`/patients/${id}`, input);
  return data;
}

export async function deletePatient(id: number): Promise<void> {
  await api.delete(`/patients/${id}`);
}

export async function uploadPatientPhoto(id: number, file: File): Promise<Patient> {
  const formData = new FormData();
  formData.append("photo", file);
  const { data } = await api.post<Patient>(`/patients/${id}/photo`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}
