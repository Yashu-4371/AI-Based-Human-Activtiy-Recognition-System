import { AlertOctagon, Clock3, CameraOff } from "lucide-react";
import { SkeletonOverlay } from "./SkeletonOverlay";
import { ActivityBadge } from "./ActivityBadge";
import type { LiveMessage } from "@/hooks/useWebSocket";

interface LiveFeedProps {
  message: LiveMessage | null;
  isConnected: boolean;
}

const FRAME_WIDTH = 960;
const FRAME_HEIGHT = 540;

export function LiveFeed({ message, isConnected }: LiveFeedProps) {
  const hasFrame = !!message?.frame_jpeg_base64;

  return (
    <div className="relative overflow-hidden rounded-xl border border-border bg-black" style={{ aspectRatio: "16/9" }}>
      {hasFrame ? (
        <img
          src={`data:image/jpeg;base64,${message!.frame_jpeg_base64}`}
          alt="Live patient monitoring feed"
          className="h-full w-full object-contain"
        />
      ) : (
        <div className="flex h-full w-full flex-col items-center justify-center gap-2 text-white/60">
          <CameraOff className="h-10 w-10" />
          <p className="text-sm">{isConnected ? "Waiting for camera feed..." : "Connecting..."}</p>
        </div>
      )}

      {hasFrame && (
        <SkeletonOverlay points={message?.skeleton_points ?? []} width={FRAME_WIDTH} height={FRAME_HEIGHT} />
      )}

      <div className="absolute left-4 top-4 flex flex-col gap-2">
        <ActivityBadge activity={message?.activity_label ?? null} confidence={message?.confidence ?? 0} />
      </div>

      <div className="absolute right-4 top-4 flex flex-col items-end gap-2">
        {message?.fall_detected && (
          <div className="flex items-center gap-1.5 rounded-full bg-destructive px-3 py-1 text-xs font-semibold text-destructive-foreground animate-pulse">
            <AlertOctagon className="h-3.5 w-3.5" />
            FALL DETECTED
          </div>
        )}
        {message?.inactivity_warning && (
          <div className="flex items-center gap-1.5 rounded-full bg-warning px-3 py-1 text-xs font-semibold text-warning-foreground">
            <Clock3 className="h-3.5 w-3.5" />
            Prolonged inactivity
          </div>
        )}
      </div>

      <div className="absolute bottom-4 left-4 rounded-md bg-black/60 px-2 py-1 font-mono text-xs text-white">
        {message?.fps?.toFixed(1) ?? "0.0"} FPS
      </div>
    </div>
  );
}
