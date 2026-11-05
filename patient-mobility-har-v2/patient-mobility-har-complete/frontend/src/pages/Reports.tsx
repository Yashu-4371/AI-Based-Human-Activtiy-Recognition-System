import * as React from "react";
import { FileDown, FileText } from "lucide-react";
import { DashboardLayout } from "@/layouts/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { usePatients } from "@/hooks/usePatients";
import { useToast } from "@/components/ui/toast";
import * as reportService from "@/services/reportService";
import type { Report, ReportFormat, ReportType } from "@/services/reportService";
import { parseServerDate } from "@/lib/utils";

export default function Reports() {
  const { patients } = usePatients();
  const { toast } = useToast();

  const [selectedPatientId, setSelectedPatientId] = React.useState<string>("");
  const [reportType, setReportType] = React.useState<ReportType>("weekly");
  const [reportFormat, setReportFormat] = React.useState<ReportFormat>("pdf");
  const [reports, setReports] = React.useState<Report[]>([]);
  const [isGenerating, setIsGenerating] = React.useState(false);
  const [downloadingId, setDownloadingId] = React.useState<number | null>(null);

  const loadReports = React.useCallback(async () => {
    const data = await reportService.listReports(selectedPatientId ? Number(selectedPatientId) : undefined);
    setReports(data);
  }, [selectedPatientId]);

  React.useEffect(() => {
    loadReports();
  }, [loadReports]);

  const handleGenerate = async () => {
    if (!selectedPatientId) {
      toast({ title: "Select a patient first", variant: "warning" });
      return;
    }
    setIsGenerating(true);
    try {
      await reportService.generateReport(Number(selectedPatientId), reportType, reportFormat);
      toast({ title: "Report generated", variant: "success" });
      loadReports();
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownload = async (reportId: number) => {
    setDownloadingId(reportId);
    try {
      await reportService.downloadReport(reportId);
    } catch {
      toast({ title: "Download failed", description: "Could not download the report. Please try again.", variant: "destructive" });
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <DashboardLayout title="Reports">
      <Card glass className="mb-6">
        <CardHeader>
          <CardTitle>Generate New Report</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-4">
          <div className="w-56 space-y-1.5">
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

          <div className="w-40 space-y-1.5">
            <label className="text-sm font-medium">Period</label>
            <Select value={reportType} onValueChange={(v) => setReportType(v as ReportType)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="daily">Daily</SelectItem>
                <SelectItem value="weekly">Weekly</SelectItem>
                <SelectItem value="monthly">Monthly</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="w-40 space-y-1.5">
            <label className="text-sm font-medium">Format</label>
            <Select value={reportFormat} onValueChange={(v) => setReportFormat(v as ReportFormat)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="pdf">PDF</SelectItem>
                <SelectItem value="csv">CSV</SelectItem>
                <SelectItem value="xlsx">Excel</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Button onClick={handleGenerate} disabled={isGenerating}>
            <FileDown className="mr-2 h-4 w-4" />
            {isGenerating ? "Generating..." : "Generate"}
          </Button>
        </CardContent>
      </Card>

      <Card glass>
        <CardHeader>
          <CardTitle>Generated Reports</CardTitle>
        </CardHeader>
        <CardContent>
          {reports.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">No reports generated yet.</p>
          ) : (
            <ul className="space-y-2">
              {reports.map((report) => (
                <li key={report.id} className="flex items-center justify-between rounded-lg border border-border p-3">
                  <div className="flex items-center gap-3">
                    <FileText className="h-4 w-4 text-primary" />
                    <div>
                      <p className="text-sm font-medium capitalize">
                        {report.report_type} report — Patient #{report.patient_id}
                      </p>
                      <p className="font-mono text-xs text-muted-foreground">
                        {parseServerDate(report.generated_at).toLocaleString()} · {report.report_format.toUpperCase()}
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={downloadingId === report.id}
                    onClick={() => handleDownload(report.id)}
                  >
                    {downloadingId === report.id ? "Downloading..." : "Download"}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </DashboardLayout>
  );
}
