import { api } from "./api";

export interface PatientSummary {
  id: number;
  name: string;
}

export interface Caregiver {
  id: number;
  full_name: string;
  phone: string;
  email: string | null;
  relationship_to_patient: string | null;
  additional_contact_info: string | null;
  created_at: string;
  patients: PatientSummary[];
}

export type CaregiverInput = {
  full_name: string;
  phone: string;
  email?: string;
  relationship_to_patient?: string;
  additional_contact_info?: string;
  patient_ids?: number[];
};

export async function listCaregivers(patientId?: number): Promise<Caregiver[]> {
  const { data } = await api.get<Caregiver[]>("/caregivers", { params: patientId ? { patient_id: patientId } : {} });
  return data;
}

export async function createCaregiver(input: CaregiverInput): Promise<Caregiver> {
  const { data } = await api.post<Caregiver>("/caregivers", input);
  return data;
}

export async function updateCaregiver(id: number, input: Partial<CaregiverInput>): Promise<Caregiver> {
  const { data } = await api.put<Caregiver>(`/caregivers/${id}`, input);
  return data;
}

export async function deleteCaregiver(id: number): Promise<void> {
  await api.delete(`/caregivers/${id}`);
}

export async function assignCaregiver(caregiverId: number, patientId: number): Promise<Caregiver> {
  const { data } = await api.post<Caregiver>(`/caregivers/${caregiverId}/assign/${patientId}`);
  return data;
}

export async function unassignCaregiver(caregiverId: number, patientId: number): Promise<Caregiver> {
  const { data } = await api.delete<Caregiver>(`/caregivers/${caregiverId}/assign/${patientId}`);
  return data;
}

export async function sendTestEmail(caregiverId: number): Promise<{ sent: boolean; recipient: string; message: string }> {
  const { data } = await api.post(`/caregivers/${caregiverId}/test-email`);
  return data;
}
