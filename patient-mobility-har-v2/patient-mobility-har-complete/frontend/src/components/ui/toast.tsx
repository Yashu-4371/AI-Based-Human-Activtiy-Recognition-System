import * as React from "react";
import { X, CheckCircle2, AlertTriangle, Info } from "lucide-react";
import { cn } from "@/lib/utils";

type ToastVariant = "default" | "success" | "destructive" | "warning";

interface ToastItem {
  id: string;
  title: string;
  description?: string;
  variant?: ToastVariant;
}

interface ToastContextValue {
  toasts: ToastItem[];
  toast: (item: Omit<ToastItem, "id">) => void;
  dismiss: (id: string) => void;
}

const ToastContext = React.createContext<ToastContextValue | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<ToastItem[]>([]);

  const dismiss = React.useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toast = React.useCallback(
    (item: Omit<ToastItem, "id">) => {
      const id = crypto.randomUUID();
      setToasts((prev) => [...prev, { ...item, id }]);
      setTimeout(() => dismiss(id), 5000);
    },
    [dismiss]
  );

  return (
    <ToastContext.Provider value={{ toasts, toast, dismiss }}>
      {children}
      <ToastViewport />
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = React.useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within a ToastProvider");
  return ctx;
}

const variantStyles: Record<ToastVariant, string> = {
  default: "border-border bg-card",
  success: "border-success/30 bg-success/10",
  destructive: "border-destructive/30 bg-destructive/10",
  warning: "border-warning/30 bg-warning/10",
};

const variantIcons: Record<ToastVariant, React.ReactNode> = {
  default: <Info className="h-5 w-5 text-primary" />,
  success: <CheckCircle2 className="h-5 w-5 text-success" />,
  destructive: <AlertTriangle className="h-5 w-5 text-destructive" />,
  warning: <AlertTriangle className="h-5 w-5 text-warning" />,
};

function ToastViewport() {
  const { toasts, dismiss } = useToast();

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={cn(
            "animate-fade-in flex items-start gap-3 rounded-lg border p-4 shadow-lg backdrop-blur-glass",
            variantStyles[t.variant ?? "default"]
          )}
        >
          {variantIcons[t.variant ?? "default"]}
          <div className="flex-1">
            <p className="text-sm font-semibold">{t.title}</p>
            {t.description && <p className="text-sm text-muted-foreground">{t.description}</p>}
          </div>
          <button onClick={() => dismiss(t.id)} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
