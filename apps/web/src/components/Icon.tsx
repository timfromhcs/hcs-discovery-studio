import type { SVGProps } from "react";

export type IconName =
  | "workspace"
  | "folder"
  | "library"
  | "workflow"
  | "run"
  | "results"
  | "models"
  | "database"
  | "settings"
  | "info"
  | "sun"
  | "moon"
  | "menu"
  | "close"
  | "plus"
  | "arrowRight"
  | "arrowLeft"
  | "search"
  | "download"
  | "copy"
  | "check"
  | "alert"
  | "x"
  | "play"
  | "stop"
  | "retry"
  | "upload"
  | "external"
  | "chevronDown"
  | "chevronRight"
  | "trash"
  | "target"
  | "cpu"
  | "clock"
  | "shield"
  | "flask"
  | "molecule"
  | "refresh"
  | "filter"
  | "sort"
  | "eye";

const paths: Record<IconName, string> = {
  workspace: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
  folder: "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  library: "M4 5h6v14H4zM10 5h4v14h-4zM15 6l4-1 2 13-4 1zM4 9h6M4 15h6",
  workflow: "M5 4h5v5H5zM14 15h5v5h-5zM7.5 9v4a2 2 0 0 0 2 2h4.5",
  run: "M3 12h4l2.5-6 4 12L16 12h5",
  results: "M4 20V9M10 20V4M16 20v-7M22 20V7",
  models: "M5 5h6v6H5zM13 5h6v6h-6zM5 13h6v6H5zM13 13h6v6h-6zM8 11v2M16 11v2M8 11h8",
  database: "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6",
  settings: "M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1z",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 10v6M12 7.2v.1",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
  moon: "M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z",
  menu: "M3 6h18M3 12h18M3 18h18",
  close: "M6 6l12 12M18 6L6 18",
  plus: "M12 5v14M5 12h14",
  arrowRight: "M5 12h14M13 6l6 6-6 6",
  arrowLeft: "M19 12H5M11 18l-6-6 6-6",
  search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3",
  download: "M12 3v12M7 10l5 5 5-5M4 21h16",
  copy: "M8 8h11v11H8zM5 16H4V4h12v1",
  check: "M4 12l5 5L20 6",
  alert: "M12 3l9.5 17H2.5zM12 9v5M12 17.5v.1",
  x: "M6 6l12 12M18 6L6 18",
  play: "M7 4l13 8-13 8z",
  stop: "M6 6h12v12H6z",
  retry: "M3 12a9 9 0 0 1 15.5-6.2L21 8M21 3v5h-5M21 12a9 9 0 0 1-15.5 6.2L3 16M3 21v-5h5",
  upload: "M12 21V9M7 14l5-5 5 5M4 4h16",
  external: "M14 4h6v6M20 4L10 14M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5",
  chevronDown: "M6 9l6 6 6-6",
  chevronRight: "M9 6l6 6-6 6",
  trash: "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v5M14 11v5",
  target: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z",
  cpu: "M7 7h10v10H7zM9 3v4M15 3v4M9 17v4M15 17v4M3 9h4M3 15h4M17 9h4M17 15h4",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z",
  flask: "M9 3h6M10 3v5l-6 10a2 2 0 0 0 1.8 3h12.4a2 2 0 0 0 1.8-3L14 8V3M8 13h8",
  molecule: "M12 5a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM5 18a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM19 18a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM11 4.5L6 14M13 4.5L18 14M7 16h10",
  refresh: "M20 11a8 8 0 0 0-13.7-4L4 9M4 4v5h5M4 13a8 8 0 0 0 13.7 4L20 15M20 20v-5h-5",
  filter: "M3 5h18l-7 8v6l-4 2v-8z",
  sort: "M8 4v16M4 8l4-4 4 4M16 20V4M12 16l4 4 4-4",
  eye: "M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
};

interface IconProps extends Omit<SVGProps<SVGSVGElement>, "name"> {
  name: IconName;
  size?: number;
}

export function Icon({ name, size = 18, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      <path d={paths[name]} />
    </svg>
  );
}

export function Logo({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" aria-hidden="true" focusable="false">
      <rect x="1.5" y="1.5" width="37" height="37" rx="10" fill="var(--brand-mark)" stroke="var(--brand-mark-border)" />
      <path d="M11 27V13M11 20h8M19 13v14" stroke="var(--brand-ink)" strokeWidth="2.2" strokeLinecap="round" />
      <circle cx="26.5" cy="15" r="2.6" fill="var(--accent)" />
      <circle cx="29" cy="25" r="2.1" fill="var(--brand-ink-2)" />
      <path d="M22 26.5l-3-4.6 5.4-4.4 1.9 4.7" stroke="var(--brand-ink-2)" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}
