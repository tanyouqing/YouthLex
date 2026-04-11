"use client";

import { useDebateState } from "../../context/DebateContext";
import { useDebate } from "../../hooks/useDebate";
import { SCENARIO_OPTIONS } from "../../types/api";
import styles from "../../styles/sidebar.module.css";

export function Sidebar() {
  const { state: { config, sessionData, isLoading }, dispatch } = useDebateState();
  const { initSession } = useDebate();

  const isSessionStarted = sessionData !== null && sessionData.round_index > 0;
  const isEnded = sessionData !== null && sessionData.should_end;
  
  // Highlighting "New Session" when ended makes it obvious what to do next
  const btnClass = `${styles.btnPrimary} ${isEnded ? styles.highlightBtn : ""}`;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    dispatch({
      type: "SET_CONFIG",
      payload: {
        [name]: name === "maxRounds" ? parseInt(value) : value,
      },
    });
  };

  return (
    <aside className={styles.sidebar}>
      <h1 className={styles.header}>Debate Partner</h1>
      
      <div className={styles.formGroup}>
        <label className={styles.label}>案情背景 (Case Background)</label>
        <textarea
          name="caseBackground"
          className={`${styles.input} ${styles.textarea}`}
          value={config.caseBackground}
          onChange={handleChange}
          disabled={isSessionStarted || isLoading}
        />
      </div>

      <div className={styles.formGroup}>
        <label className={styles.label}>纠纷场景 (Scenario)</label>
        <select
          name="scenarioHint"
          className={styles.input}
          value={config.scenarioHint}
          onChange={handleChange}
          disabled={isSessionStarted || isLoading}
        >
          {SCENARIO_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      <div className={styles.formGroup}>
        <label className={styles.label}>最大轮次 (Max Rounds)</label>
        <input
          type="number"
          name="maxRounds"
          className={styles.input}
          value={config.maxRounds}
          onChange={handleChange}
          min={1}
          max={20}
          disabled={isSessionStarted || isLoading}
        />
      </div>

      <button
        className={btnClass}
        onClick={initSession}
        disabled={isLoading}
      >
        [ 新建会话 ]
      </button>

      <div style={{ marginTop: "auto", fontSize: "0.75rem", color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>
        SYSTEM: DEBATE_AGENT_V1
        <br/>MODE: STRICT
      </div>
    </aside>
  );
}
