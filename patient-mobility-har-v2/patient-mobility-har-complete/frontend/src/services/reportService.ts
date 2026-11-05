import { api } from "./api";

export type ReportType = "daily" | "weekly" | "monthly";
export type ReportFormat = "pdf" | "csv" | "xlsx";

export interface Report {
  id: number;
  patient_id: number;
  report_type: ReportType;
  report_format: ReportFormat;
  file_path: string;
  generated_at: string;
}

export async function generateReport(
  patient_id: number,
  report_type: ReportType,
  report_format: ReportFormat = "pdf"
): Promise<Report> {
  const { data } = await api.post<Report>("/reports/generate", { patient_id, report_type, report_format });
  return data;
}

export async function listReports(patient_id?: number): Promise<Report[]> {
  const { data } = await api.get<Report[]>("/reports", { params: { patient_id } });
  return data;
}

/**
 * Downloads a report through the authenticated API client (so the JWT
 * bearer token actually gets attached — a plain <a href> tag bypasses
 * axios's auth interceptor entirely and the backend correctly 401s),
 * then saves it via a temporary blob link. Reads the real filename the
 * backend generated (Content-Disposition) rather than guessing one.
 */
export async function downloadReport(reportId: number): Promise<void> {
  const response = await api.get(`/reports/${reportId}/download`, { responseType: "blob" });

  const disposition: string | undefined = response.headers["content-disposition"];
  const filenameMatch = disposition?.match(/filename="?([^"]+)"?/);
  const filename = filenameMatch?.[1] ?? `report_${reportId}`;

  const blobUrl = window.URL.createObjectURL(response.data as Blob);
  const link = document.createElement("a");
  link.href = blobUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(blobUrl);
}
