"use client";

import { useTheme } from "../../context/ThemeContext";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <button 
      onClick={toggleTheme}
      style={{
        background: "var(--bg-tertiary)",
        border: "1px solid var(--border)",
        color: "var(--text-primary)",
        padding: "4px 8px",
        cursor: "pointer",
        fontFamily: "var(--font-mono)",
        fontSize: "0.8rem",
        fontWeight: "bold"
      }}
      title="Toggle Theme"
    >
      {theme === "light" ? "🌙 DARK" : "☀ LIGHT"}
    </button>
  );
}
