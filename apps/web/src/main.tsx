import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles/global.css";

const container = document.getElementById("root");
if (!container) {
  throw new Error("Root element #root is missing from index.html");
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

/**
 * Register the offline shell. Production only: a service worker in front of the dev
 * server would cache Vite's unbundled modules and make hot reload lie about what is
 * on disk. A failed registration is not fatal — the app works, it just needs the
 * network, and the offline lab says so.
 */
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js")
      .then(() => navigator.serviceWorker.ready)
      .then((registration) => {
        // The first visit happens before the worker controls the page; hand it the
        // URLs that booted this page so an offline reload has a complete shell.
        const urls = [...document.querySelectorAll<HTMLScriptElement | HTMLLinkElement>("script[src], link[rel=stylesheet], link[rel=modulepreload]")]
          .map((element) => ("src" in element ? element.src : element.href))
          .filter((url) => url.startsWith(window.location.origin));
        (registration.active ?? navigator.serviceWorker.controller)?.postMessage({ type: "CACHE_URLS", urls });
      })
      .catch(() => {
        /* offline mode unavailable; online behaviour is unchanged */
      });
  });
}
