import { motion } from "framer-motion";
import { type LucideIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  tone?: "default" | "destructive" | "warning" | "success";
  delay?: number;
}

const toneStyles: Record<NonNullable<StatCardProps["tone"]>, string> = {
  default: "bg-primary/10 text-primary",
  destructive: "bg-destructive/10 text-destructive",
  warning: "bg-warning/10 text-warning",
  success: "bg-success/10 text-success",
};

export function StatCard({ label, value, icon: Icon, tone = "default", delay = 0 }: StatCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay }}
    >
      <Card glass className="overflow-hidden">
        <CardContent className="flex items-center justify-between p-5">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
            <p className="mt-1 font-mono text-2xl font-semibold">{value}</p>
          </div>
          <div className={cn("flex h-11 w-11 items-center justify-center rounded-lg", toneStyles[tone])}>
            <Icon className="h-5 w-5" />
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}
