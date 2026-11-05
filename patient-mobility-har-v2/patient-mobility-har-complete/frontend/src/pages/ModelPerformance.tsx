
import {
  Activity,
  Brain,
  CheckCircle2,
  Gauge,
  Target,
} from "lucide-react";

import { DashboardLayout } from "@/layouts/DashboardLayout";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const labels = ["Lying", "Sitting", "Standing", "Walking"];

// Illustrative confusion matrix: 4,800 total samples
// 1,200 samples for each activity.
const confusionMatrix = [
  [1117, 30, 30, 23],
  [25, 1110, 40, 25],
  [20, 43, 1102, 35],
  [20, 32, 35, 1113],
];

function formatPercentage(value: number) {
  return `${(value * 100).toFixed(2)}%`;
}

export default function ModelPerformance() {
  const totalSamples = confusionMatrix
    .flat()
    .reduce((sum, value) => sum + value, 0);

  const correctPredictions = confusionMatrix.reduce(
    (sum, row, index) => sum + row[index],
    0
  );

  const accuracy = correctPredictions / totalSamples;

  const rowTotals = confusionMatrix.map((row) =>
    row.reduce((sum, value) => sum + value, 0)
  );

  const columnTotals = labels.map((_, columnIndex) =>
    confusionMatrix.reduce(
      (sum, row) => sum + row[columnIndex],
      0
    )
  );

  const classificationReport = labels.map((activity, index) => {
    const truePositive = confusionMatrix[index][index];
    const precision = truePositive / columnTotals[index];
    const recall = truePositive / rowTotals[index];
    const f1 =
      precision + recall === 0
        ? 0
        : (2 * precision * recall) / (precision + recall);

    return {
      activity,
      precision,
      recall,
      f1,
      support: rowTotals[index],
    };
  });

  const macroPrecision =
    classificationReport.reduce(
      (sum, item) => sum + item.precision,
      0
    ) / labels.length;

  const macroRecall =
    classificationReport.reduce(
      (sum, item) => sum + item.recall,
      0
    ) / labels.length;

  const macroF1 =
    classificationReport.reduce(
      (sum, item) => sum + item.f1,
      0
    ) / labels.length;

  const metrics = [
    {
      label: "Accuracy",
      value: formatPercentage(accuracy),
      icon: Target,
    },
    {
      label: "Precision",
      value: formatPercentage(macroPrecision),
      icon: CheckCircle2,
    },
    {
      label: "Recall",
      value: formatPercentage(macroRecall),
      icon: Gauge,
    },
    {
      label: "F1 Score",
      value: formatPercentage(macroF1),
      icon: Activity,
    },
  ];

  const maximum = Math.max(...confusionMatrix.flat());

  return (
    <DashboardLayout title="Model Performance">
      <div className="space-y-6">

        {/* Page Heading */}
        <div>
          <div className="flex items-center gap-2">
            <Brain className="h-6 w-6 text-primary" />
            <h2 className="text-xl font-bold">
              AI Model Evaluation
            </h2>
          </div>

          <p className="mt-1 text-sm text-muted-foreground">
            Human Activity Recognition - Random Forest Classifier
          </p>

          <p className="mt-2 text-xs text-amber-600">
            
          </p>
        </div>

        {/* Performance Metrics */}
        <Card glass>
          <CardHeader>
            <CardTitle>Performance Metrics</CardTitle>
          </CardHeader>

          <CardContent>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {metrics.map((metric) => {
                const Icon = metric.icon;

                return (
                  <div
                    key={metric.label}
                    className="rounded-xl border border-border bg-secondary/40 p-4"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">
                        {metric.label}
                      </span>

                      <Icon className="h-5 w-5 text-primary" />
                    </div>

                    <p className="mt-3 text-2xl font-bold">
                      {metric.value}
                    </p>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Confusion Matrix */}
        <Card glass>
          <CardHeader>
            <CardTitle>Confusion Matrix</CardTitle>

            <p className="text-sm text-muted-foreground">
              Rows represent actual activities. Columns represent
              predicted activities. Diagonal values are correct
              predictions.
            </p>
          </CardHeader>

          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-center text-sm">
                <thead>
                  <tr>
                    <th className="border border-border p-3 text-muted-foreground">
                      Actual / Predicted
                    </th>

                    {labels.map((label) => (
                      <th
                        key={label}
                        className="border border-border p-3"
                      >
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>

                <tbody>
                  {confusionMatrix.map((row, rowIndex) => (
                    <tr key={labels[rowIndex]}>
                      <th className="border border-border p-3">
                        {labels[rowIndex]}
                      </th>

                      {row.map((value, columnIndex) => {
                        const intensity = value / maximum;

                        return (
                          <td
                            key={columnIndex}
                            className="border border-border p-4 font-semibold"
                            style={{
                              backgroundColor: `rgba(59, 130, 246, ${
                                0.06 + intensity * 0.55
                              })`,
                            }}
                          >
                            {value.toLocaleString("en-IN")}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="mt-3 text-xs text-muted-foreground">
              Darker cells represent larger numbers of predictions.
            </p>
          </CardContent>
        </Card>

        {/* Classification Report */}
        <Card glass>
          <CardHeader>
            <CardTitle>Classification Report</CardTitle>

            <p className="text-sm text-muted-foreground">
              Performance for each recognized activity.
            </p>
          </CardHeader>

          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="p-3">Activity</th>
                    <th className="p-3">Precision</th>
                    <th className="p-3">Recall</th>
                    <th className="p-3">F1 Score</th>
                    <th className="p-3">Support</th>
                  </tr>
                </thead>

                <tbody>
                  {classificationReport.map((item) => (
                    <tr
                      key={item.activity}
                      className="border-b border-border"
                    >
                      <td className="p-3 font-medium">
                        {item.activity}
                      </td>

                      <td className="p-3">
                        {formatPercentage(item.precision)}
                      </td>

                      <td className="p-3">
                        {formatPercentage(item.recall)}
                      </td>

                      <td className="p-3">
                        {formatPercentage(item.f1)}
                      </td>

                      <td className="p-3">
                        {item.support.toLocaleString("en-IN")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="mt-4 text-xs text-muted-foreground">
              Total illustrative samples: {totalSamples.toLocaleString("en-IN")}
              {" "} | Correct predictions: {correctPredictions.toLocaleString("en-IN")}
            </p>
          </CardContent>
        </Card>

      </div>
    </DashboardLayout>
  );
}
