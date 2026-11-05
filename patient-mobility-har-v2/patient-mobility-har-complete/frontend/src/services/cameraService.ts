import { api } from "./api";

export interface CameraStatus {
  is_running: boolean;
  camera_connected: boolean;
  fps: number;
  activity_label: string | null;
  confidence: number;
  fall_detected: boolean;
  inactivity_warning: boolean;
  updated_at: string | null;
}

export interface CameraSetting {
  id: number;
  name: string;
  source_type: "webcam" | "usb" | "ip" | "rtsp";
  source_uri: string;
  resolution_width: number;
  resolution_height: number;
  is_active: boolean;
}

export async function getCameraStatus(): Promise<CameraStatus> {
  const { data } = await api.get<CameraStatus>("/camera/status");
  return data;
}

export async function startCamera(patient_id: number, camera_id: number): Promise<{ message: string }> {
  const { data } = await api.post("/camera/start", { patient_id, camera_id });
  return data;
}

export async function stopCamera(): Promise<{ message: string }> {
  const { data } = await api.post("/camera/stop");
  return data;
}

export async function listCameraSettings(): Promise<CameraSetting[]> {
  const { data } = await api.get<CameraSetting[]>("/camera/settings");
  return data;
}

export async function updateCameraSetting(id: number, update: Partial<CameraSetting>): Promise<CameraSetting> {
  const { data } = await api.put<CameraSetting>(`/camera/settings/${id}`, update);
  return data;
}
