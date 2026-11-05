import { Footprints, User, Armchair, BedDouble } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface ActivityBadgeProps {
  activity: string | null;
  confidence: number;
}

const activityIcons: Record<string, React.ElementType> = {
  walking: Footprints,
  standing: User,
  sitting: Armchair,
  lying: BedDouble,
};

export function ActivityBadge({ activity, confidence }: ActivityBadgeProps) {
  if (!activity) {
    return <Badge variant="secondary">No patient detected</Badge>;
  }

  const Icon = activityIcons[activity] ?? User;

  return (
    <Badge variant="default" className="gap-1.5 px-3 py-1 text-sm">
      <Icon className="h-3.5 w-3.5" />
      <span className="capitalize">{activity}</span>
      <span className="font-mono text-primary-foreground/80">{(confidence * 100).toFixed(1)}%</span>
    </Badge>
  );
}
