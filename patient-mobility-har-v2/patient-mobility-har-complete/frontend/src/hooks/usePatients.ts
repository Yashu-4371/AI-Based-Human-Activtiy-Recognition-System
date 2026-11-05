import * as React from "react";
import * as patientService from "@/services/patientService";
import type { Patient } from "@/services/patientService";

export function usePatients() {
  const [patients, setPatients] = React.useState<Patient[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const refresh = React.useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await patientService.listPatients();
      setPatients(data);
    } catch (err) {
      setError("Failed to load patients.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  return { patients, isLoading, error, refresh };
}
