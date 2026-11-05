import * as React from "react";

interface SkeletonOverlayProps {
  points: [number, number][];
  width: number;
  height: number;
}

// MediaPipe Pose connections (subset relevant to the tracked joints), as
// pairs of landmark indices, mirroring app/ml/pose_estimator.py on the backend.
const CONNECTIONS: [number, number][] = [
  [11, 12], // shoulders
  [11, 13], [13, 15], // left arm
  [12, 14], [14, 16], // right arm
  [11, 23], [12, 24], // torso sides
  [23, 24], // hips
  [23, 25], [25, 27], // left leg
  [24, 26], [26, 28], // right leg
];

export function SkeletonOverlay({ points, width, height }: SkeletonOverlayProps) {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, width, height);
    if (points.length === 0) return;

    ctx.strokeStyle = "#0EA5E9";
    ctx.lineWidth = 3;
    ctx.fillStyle = "#1D4ED8";

    CONNECTIONS.forEach(([a, b]) => {
      const pointA = points[a];
      const pointB = points[b];
      if (!pointA || !pointB) return;
      ctx.beginPath();
      ctx.moveTo(pointA[0] * width, pointA[1] * height);
      ctx.lineTo(pointB[0] * width, pointB[1] * height);
      ctx.stroke();
    });

    points.forEach(([x, y]) => {
      ctx.beginPath();
      ctx.arc(x * width, y * height, 4, 0, Math.PI * 2);
      ctx.fill();
    });
  }, [points, width, height]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      className="pointer-events-none absolute inset-0 h-full w-full"
    />
  );
}
