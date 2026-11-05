import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * The backend stores times in UTC and sends them WITHOUT a timezone suffix
 * (e.g. "2026-10-12T11:55:33"). `new Date()` would read that as local time and
 * show the wrong hour, so mark it as UTC first.
 */
export function parseServerDate(value: string): Date {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  return new Date(hasZone ? value : `${value}Z`);
}
