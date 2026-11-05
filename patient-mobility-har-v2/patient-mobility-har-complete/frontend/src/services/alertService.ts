import { api } from "./api";

export type AlertType = "fall" | "inactivity" | "abnormal";
export type AlertPriority = "critical" | "warning" | "normal";
export type AlertStatus = "open" | "resolved";

export type EmailDeliveryStatus = "pending" | "sent" | "failed" | "skipped";

export interface EmailDelivery {
  id: number;
  caregiver_id: number | null;
  status: EmailDeliveryStatus;
  detail: string | null;
  created_at: string;
  sent_at: string | null;
}

export interface Alert {
  id: number;
  patient_id: number;
  type: AlertType;
  priority: AlertPriority;
  status: AlertStatus;
  message: string;
  screenshot_path: string | null;
  created_at: string;
  resolved_at: string | null;
  resolved_by: number | null;
  email_deliveries: EmailDelivery[];
}

export interface AlertFilters {
  patient_id?: number;
  status?: AlertStatus;
  priority?: AlertPriority;
}

export async function listAlerts(filters: AlertFilters = {}): Promise<Alert[]> {
  const { data } = await api.get<Alert[]>("/alerts", { params: filters });
  return data;
}

export async function resolveAlert(id: number, resolution_notes?: string): Promise<Alert> {
  const { data } = await api.patch<Alert>(`/alerts/${id}/resolve`, { resolution_notes });
  return data;
}
