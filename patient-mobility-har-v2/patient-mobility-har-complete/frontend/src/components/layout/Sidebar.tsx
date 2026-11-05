import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Video,
  Users,
  FileBarChart,
  PieChart,
  Activity,
  HeartHandshake,
  Brain,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { PulseLine } from "./PulseLine";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/live-monitor", label: "Live Monitor", icon: Video },
  { to: "/patients", label: "Patients", icon: Users },
  { to: "/caregivers", label: "Caregivers", icon: HeartHandshake },
  { to: "/reports", label: "Reports", icon: FileBarChart },
  { to: "/analytics", label: "Analytics", icon: PieChart },
  { to: "/model-performance", label: "Model Performance", icon: Brain },
];

export function Sidebar() {
  return (
    <aside className="hidden md:flex md:w-64 md:flex-col border-r border-border bg-card/50">
      <div className="flex items-center gap-2 px-6 py-6">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Activity className="h-5 w-5" />
        </div>
        <div>
          <p className="font-display text-sm font-bold leading-tight">
            MobilityWatch
          </p>
          <p className="text-[11px] text-muted-foreground leading-tight">
            Patient Monitoring
          </p>
        </div>
      </div>

      <PulseLine className="h-6 w-full px-6 text-accent/60" />

      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:bg-secondary hover:text-foreground"
              )
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="px-6 py-4 text-[11px] text-muted-foreground border-t border-border">
        AI-Based Human Activity Recognition
      </div>
    </aside>
  );
}