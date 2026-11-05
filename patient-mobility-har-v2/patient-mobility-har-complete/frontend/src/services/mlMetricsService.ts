
import { api } from "./api";

export interface PerClassMetric {
  precision: number;
  recall: number;
  f1_score: number;
  support: number;
}

export interface MLMetrics {
  trained_at?: string;
  data_source?: string;
  split_method?: string;
  generalization_evidence?: string;
  accuracy?: number;
  precision_macro?: number;
  recall_macro?: number;
  f1_macro?: number;
  per_class?: Record<string, PerClassMetric>;
  confusion_matrix?: number[][];
  confusion_matrix_labels?: string[];
  labels?: string[];
  n_test_samples?: number;
  n_total_samples?: number;
  limitations?: string[];
}

export async function getMLMetrics(): Promise<MLMetrics> {
  const response = await api.get<MLMetrics>("/ml/metrics");
  return response.data;
}
