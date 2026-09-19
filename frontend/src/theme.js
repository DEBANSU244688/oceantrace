import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "oceantrace-theme";

function read() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // private windows and blocked site data both throw here; fall through to
    // the system preference rather than breaking the app over a stored string
  }
  return null;
}

function systemTheme() {
  return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

/**
 * Theme state for the app. Starts from the viewer's OS preference, remembers an
 * explicit choice, and keeps following the OS until one is made.
 *
 * The value is mirrored onto <html data-theme> because the stylesheet keys off
 * that attribute; the hook's return value is for the map, whose layer colours
 * are passed to Leaflet as strings and so cannot come from CSS variables.
 */
export function useTheme() {
  const [theme, setTheme] = useState(() => read() ?? systemTheme());
  const [explicit, setExplicit] = useState(() => read() !== null);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    if (explicit) return undefined;
    const mq = window.matchMedia?.("(prefers-color-scheme: light)");
    if (!mq) return undefined;
    const onChange = (e) => setTheme(e.matches ? "light" : "dark");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [explicit]);

  const toggle = useCallback(() => {
    setTheme((current) => {
      const next = current === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        // not being able to remember the choice is not a reason to refuse it
      }
      return next;
    });
    setExplicit(true);
  }, []);

  return { theme, toggle };
}
