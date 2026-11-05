import * as React from "react";
import { Moon, Sun, LogOut, Menu } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";

interface TopbarProps {
  title: string;
  onMenuClick?: () => void;
}

export function Topbar({ title, onMenuClick }: TopbarProps) {
  const { user, logout } = useAuth();
  const [isDark, setIsDark] = React.useState(false);

  React.useEffect(() => {
    const stored = document.documentElement.classList.contains("dark");
    setIsDark(stored);
  }, []);

  const toggleDarkMode = () => {
    document.documentElement.classList.toggle("dark");
    setIsDark(document.documentElement.classList.contains("dark"));
  };

  const initials = user?.name
    ?.split(" ")
    .map((part) => part[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <header className="flex items-center justify-between border-b border-border bg-card/50 px-4 py-4 md:px-8">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" className="md:hidden" onClick={onMenuClick}>
          <Menu className="h-5 w-5" />
        </Button>
        <h1 className="font-display text-xl font-bold">{title}</h1>
      </div>

      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={toggleDarkMode} aria-label="Toggle dark mode">
          {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>

        <div className="flex items-center gap-2 pl-2">
          <Avatar>
            <AvatarFallback>{initials ?? "U"}</AvatarFallback>
          </Avatar>
          <div className="hidden sm:block text-sm">
            <p className="font-medium leading-tight">{user?.name}</p>
            <p className="text-xs capitalize text-muted-foreground leading-tight">{user?.role}</p>
          </div>
        </div>

        <Button variant="ghost" size="icon" onClick={logout} aria-label="Log out">
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
