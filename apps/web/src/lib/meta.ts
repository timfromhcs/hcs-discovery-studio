import { useEffect } from "react";

/**
 * Per-route document metadata for a single-page app.
 *
 * A SPA serves one HTML document, so title, description, canonical URL and the
 * social-preview tags have to be set on navigation. Search engines execute the
 * bundle these days, but link unfurlers do not always; both get a correct answer
 * from the same table. Declared here in one place so a new route cannot ship
 * without a description.
 */

export interface PageMeta {
  title: string;
  description: string;
}

const DEFAULT_TITLE = "HCS Discovery Studio";

export const ROUTE_META: Array<{ pattern: RegExp; meta: PageMeta }> = [
  {
    pattern: /^\/$/,
    meta: {
      title: `${DEFAULT_TITLE} — local-first drug-discovery workbench`,
      description:
        "Open, reproducible computational drug-discovery workbench: import a library, triage it, run docking, and inspect every result. Runs locally; no account, no cloud key.",
    },
  },
  {
    pattern: /^\/lab/,
    meta: {
      title: `Offline lab — ${DEFAULT_TITLE}`,
      description:
        "Import a compound library and run descriptors, triage, ranking and Tanimoto similarity entirely in your browser. Nothing is uploaded; the stored copy stays on this device.",
    },
  },
  {
    pattern: /^\/models/,
    meta: {
      title: `Model registry — ${DEFAULT_TITLE}`,
      description:
        "Every chemistry and science engine with its real status: available, host-dependent or planned. No model is labelled usable without a probe.",
    },
  },
  {
    pattern: /^\/sources/,
    meta: {
      title: `Data sources — ${DEFAULT_TITLE}`,
      description: "Policy-gated PubChem and ChEMBL connectors, plus CSV, SDF and SMILES import.",
    },
  },
  {
    pattern: /^\/settings/,
    meta: {
      title: `Settings and diagnostics — ${DEFAULT_TITLE}`,
      description:
        "Read-only configuration, storage, machine diagnostics and the browser-compute self-tests (RDKit WebAssembly, WebGPU Tanimoto).",
    },
  },
  {
    pattern: /^\/about/,
    meta: {
      title: `About and limitations — ${DEFAULT_TITLE}`,
      description:
        "What this workbench does, what it does not do, and how to check every claim. Docking is checked on one complex, property estimates are weak, and the page says so.",
    },
  },
  {
    pattern: /^\/projects\//,
    meta: {
      title: `Project — ${DEFAULT_TITLE}`,
      description: "Datasets, workflows, runs and results for one project.",
    },
  },
  {
    pattern: /^\/runs\//,
    meta: {
      title: `Run — ${DEFAULT_TITLE}`,
      description: "Node statuses, events, logs and artifacts for one run.",
    },
  },
  {
    pattern: /^\/compounds\//,
    meta: {
      title: `Compound — ${DEFAULT_TITLE}`,
      description: "Descriptors, depiction and provenance for one compound.",
    },
  },
];

const FALLBACK: PageMeta = {
  title: `Page not found — ${DEFAULT_TITLE}`,
  description: "This route does not exist. Use the workspace to continue.",
};

export function metaFor(pathname: string): PageMeta {
  return ROUTE_META.find((entry) => entry.pattern.test(pathname))?.meta ?? FALLBACK;
}

function setMeta(selector: string, attribute: "name" | "property", key: string, content: string) {
  let element = document.head.querySelector<HTMLMetaElement>(selector);
  if (!element) {
    element = document.createElement("meta");
    element.setAttribute(attribute, key);
    document.head.appendChild(element);
  }
  element.setAttribute("content", content);
}

export function applyMeta(pathname: string, origin: string = window.location.origin): PageMeta {
  const meta = metaFor(pathname);
  const url = `${origin}${pathname === "/" ? "/" : pathname}`;
  document.title = meta.title;
  setMeta('meta[name="description"]', "name", "description", meta.description);
  setMeta('meta[property="og:title"]', "property", "og:title", meta.title);
  setMeta('meta[property="og:description"]', "property", "og:description", meta.description);
  setMeta('meta[property="og:url"]', "property", "og:url", url);
  setMeta('meta[name="twitter:title"]', "name", "twitter:title", meta.title);
  setMeta('meta[name="twitter:description"]', "name", "twitter:description", meta.description);
  let canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!canonical) {
    canonical = document.createElement("link");
    canonical.rel = "canonical";
    document.head.appendChild(canonical);
  }
  canonical.href = url;
  return meta;
}

export function usePageMeta(pathname: string): void {
  useEffect(() => {
    applyMeta(pathname);
  }, [pathname]);
}
