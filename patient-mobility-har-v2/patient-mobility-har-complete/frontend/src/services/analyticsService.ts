import { api } from "./api";

export interface ActivityDistribution {
  walking: number;
  standing: number;
  sitting: number;
  lying: number;
}

export interface DailyTrendPoint {
  date: string;
  total_duration_sec: number;
}

export async function getActivityDistribution(patient_id: number, days = 7): Promise<ActivityDistribution> {
  const { data } = await api.get<ActivityDistribution>("/analytics/activity-distribution", {
    params: { patient_id, days },
  });
  return data;
}

export async function getWeeklyTrend(patient_id: number, days = 7): Promise<DailyTrendPoint[]> {
  const { data } = await api.get<DailyTrendPoint[]>("/analytics/weekly-trend", { params: { patient_id, days } });
  return data;
}

export async function getFallFrequency(patient_id: number, days = 30): Promise<{ fall_count: number }> {
  const { data } = await api.get("/analytics/fall-frequency", { params: { patient_id, days } });
  return data;
}

export async function getAverageWalkingTime(patient_id: number, days = 7): Promise<{ average_walking_seconds_per_day: number }> {
  const { data } = await api.get("/analytics/average-walking-time", { params: { patient_id, days } });
  return data;
}
