import * as React from "react";
import { Footprints, AlertOctagon } from "lucide-react";
import { DashboardLayout } from "@/layouts/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatCard } from "@/components/dashboard/StatCard";
import {
  ActivityDistributionChart,
  WeeklyTrendChart,
  ActivityDurationBarChart,
} from "@/components/dashboard/ActivityChart";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { usePatients } from "@/hooks/usePatients";
import * as analyticsService from "@/services/analyticsService";
import type { ActivityDistribution, DailyTrendPoint } from "@/services/analyticsService";

export default function Analytics() {
  const { patients } = usePatients();
  const [selectedPatientId, setSelectedPatientId] = React.useState<string>("");
  const [distribution, setDistribution] = React.useState<ActivityDistribution | null>(null);
  const [trend, setTrend] = React.useState<DailyTrendPoint[]>([]);
  const [fallCount, setFallCount] = React.useState(0);
  const [avgWalkingSec, setAvgWalkingSec] = React.useState(0);

  React.useEffect(() => {
    if (patients.length > 0 && !selectedPatientId) {
      setSelectedPatientId(String(patients[0].id));
    }
  }, [patients, selectedPatientId]);

  React.useEffect(() => {
    if (!selectedPatientId) return;
    const patientId = Number(selectedPatientId);

    Promise.all([
      analyticsService.getActivityDistribution(patientId),
      analyticsService.getWeeklyTrend(patientId),
      analyticsService.getFallFrequency(patientId),
      analyticsService.getAverageWalkingTime(patientId),
    ]).then(([dist, weeklyTrend, falls, avgWalk]) => {
      setDistribution(dist);
      setTrend(weeklyTrend);
      setFallCount(falls.fall_count);
      setAvgWalkingSec(avgWalk.average_walking_seconds_per_day);
    });
  }, [selectedPatientId]);

  const distributionData = distribution
    ? Object.entries(distribution).map(([name, value]) => ({ name, value: Math.round(value / 60) }))
    : [];

  return (
    <DashboardLayout title="Analytics">
      <div className="mb-6 w-56 space-y-1.5">
        <label className="text-sm font-medium">Patient</label>
        <Select value={selectedPatientId} onValueChange={setSelectedPatientId}>
          <SelectTrigger>
            <SelectValue placeholder="Select patient" />
          </SelectTrigger>
          <SelectContent>
            {patients.map((p) => (
              <SelectItem key={p.id} value={String(p.id)}>
                {p.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <StatCard label="Fall Events (30d)" value={fallCount} icon={AlertOctagon} tone="destructive" />
        <StatCard
          label="Avg. Walking Time / Day"
          value={`${Math.round(avgWalkingSec / 60)} min`}
          icon={Footprints}
          tone="success"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card glass>
          <CardHeader>
            <CardTitle>Activity Distribution (minutes)</CardTitle>
          </CardHeader>
          <CardContent>
            <ActivityDistributionChart data={distributionData} />
          </CardContent>
        </Card>

        <Card glass>
          <CardHeader>
            <CardTitle>Activity Duration Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <ActivityDurationBarChart data={distributionData} />
          </CardContent>
        </Card>

        <Card glass className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Weekly Trend (total active seconds/day)</CardTitle>
          </CardHeader>
          <CardContent>
            <WeeklyTrendChart data={trend} />
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
