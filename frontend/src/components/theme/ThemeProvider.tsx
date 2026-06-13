import {
  createContext,
  useContext,
  useEffect,
  useState,
  type PropsWithChildren,
} from "react";

export type ThemeMode = "light" | "dark";
export type ThemeColor = "zinc" | "green" | "blue" | "violet" | "orange" | "slate";

interface ThemeContextValue {
  mode: ThemeMode;
  color: ThemeColor;
  toggleMode: () => void;
  setMode: (mode: ThemeMode) => void;
  setColor: (color: ThemeColor) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);
const STORAGE_KEY = "aptrades-theme";

function readStored(): { mode: ThemeMode; color: ThemeColor } {
  if (typeof localStorage !== "undefined") {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<{ mode: ThemeMode; color: ThemeColor }>;
        return {
          mode: parsed.mode === "light" ? "light" : "dark",
          color: (parsed.color as ThemeColor) ?? "zinc",
        };
      }
    } catch {
      /* ignore corrupt storage */
    }
  }
  // Futuristic theme defaults to dark mode.
  return { mode: "dark", color: "zinc" };
}

function applyTheme(mode: ThemeMode, color: ThemeColor) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.classList.toggle("dark", mode === "dark");
  root.setAttribute("data-theme", color);
}

export function ThemeProvider({ children }: PropsWithChildren) {
  const [{ mode, color }, setState] = useState(readStored);

  useEffect(() => {
    applyTheme(mode, color);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ mode, color }));
    } catch {
      /* ignore storage failures */
    }
  }, [mode, color]);

  const value: ThemeContextValue = {
    mode,
    color,
    toggleMode: () =>
      setState((s) => ({ ...s, mode: s.mode === "light" ? "dark" : "light" })),
    setMode: (m) => setState((s) => ({ ...s, mode: m })),
    setColor: (c) => setState((s) => ({ ...s, color: c })),
  };

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return ctx;
}
