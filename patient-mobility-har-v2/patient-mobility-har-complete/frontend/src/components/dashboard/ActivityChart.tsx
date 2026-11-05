import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

const PALETTE = ["#1D4ED8", "#0EA5E9", "#16A34A", "#D97706"];

interface DistributionChartProps {
  data: { name: string; value: number }[];
}

export function ActivityDistributionChart({ data }: DistributionChartProps) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={60} outerRadius={90} paddingAngle={3}>
          {data.map((_, index) => (
            <Cell key={index} fill={PALETTE[index % PALETTE.length]} />
          ))}
        </Pie>
        <Tooltip />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}

interface TrendChartProps {
  data: { date: string; total_duration_sec: number }[];
}

export function WeeklyTrendChart({ data }: TrendChartProps) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis dataKey="date" fontSize={12} stroke="hsl(var(--muted-foreground))" />
        <YAxis fontSize={12} stroke="hsl(var(--muted-foreground))" />
        <Tooltip />
        <Line type="monotone" dataKey="total_duration_sec" stroke="#1D4ED8" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

interface DurationBarChartProps {
  data: { name: string; value: number }[];
}

export function ActivityDurationBarChart({ data }: DurationBarChartProps) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
        <XAxis dataKey="name" fontSize={12} stroke="hsl(var(--muted-foreground))" />
        <YAxis fontSize={12} stroke="hsl(var(--muted-foreground))" />
        <Tooltip />
        <Bar dataKey="value" fill="#0EA5E9" radius={[6, 6, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
