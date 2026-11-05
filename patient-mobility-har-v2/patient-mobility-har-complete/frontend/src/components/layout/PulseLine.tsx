interface PulseLineProps {
  className?: string;
  animated?: boolean;
}

/**
 * The project's signature visual motif: an ECG-style waveform, since this
 * system's entire purpose is watching for meaningful signal in continuous
 * movement data. Used in the sidebar logo and as a "live" indicator.
 */
export function PulseLine({ className, animated = true }: PulseLineProps) {
  return (
    <svg viewBox="0 0 240 40" fill="none" className={className} xmlns="http://www.w3.org/2000/svg">
      <path
        d="M0 20 H70 L82 6 L94 34 L106 12 L116 20 H240"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray={animated ? "240" : undefined}
        className={animated ? "animate-pulse-line" : undefined}
      />
    </svg>
  );
}
