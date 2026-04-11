"use client";

import React, { useState } from "react";
import { useDebateState } from "../../context/DebateContext";
import styles from "../../styles/debug.module.css";

export function DebugDrawer() {
  const [isOpen, setIsOpen] = useState(false);
  const { state: { sessionData } } = useDebateState();

  if (!sessionData) return null;

  return (
    <div className={styles.debugContainer}>
      <div className={styles.debugHeader}>
        <button className={styles.toggleBtn} onClick={() => setIsOpen(!isOpen)}>
          🔧 DEBUG PANEL {isOpen ? "[-]" : "[+]"}
        </button>
      </div>

      {isOpen && (
        <div className={styles.debugContent}>
          <div className={styles.debugSection}>
            <div className={styles.debugTitle}>Session Control</div>
            <div className={styles.debugRow}><span className={styles.debugLabel}>End Reason Code:</span><span className={styles.debugVal}>{sessionData.end_reason_code}</span></div>
            <div className={styles.debugRow}><span className={styles.debugLabel}>Should End:</span><span className={styles.debugVal}>{String(sessionData.should_end)}</span></div>
            <div className={styles.debugRow}><span className={styles.debugLabel}>Round Index:</span><span className={styles.debugVal}>{sessionData.round_index}</span></div>
          </div>

          <div className={styles.debugSection}>
            <div className={styles.debugTitle}>Attack Target</div>
            <div className={styles.debugRow}><span className={styles.debugLabel}>Category:</span><span className={styles.debugVal}>{sessionData.attack_target_category || "N/A"}</span></div>
            <div className={styles.debugRow}><span className={styles.debugLabel}>Source:</span><span className={styles.debugVal}>{sessionData.attack_target_source || "N/A"}</span></div>
          </div>

          <div className={styles.debugSection}>
            <div className={styles.debugTitle}>Retrieval</div>
            <div className={styles.debugRow}><span className={styles.debugLabel}>Mode:</span><span className={styles.debugVal}>{sessionData.retrieval_mode || "N/A"}</span></div>
            <div className={styles.debugRow}><span className={styles.debugLabel}>Sufficiency:</span><span className={styles.debugVal}>{String(sessionData.knowledge_sufficiency)}</span></div>
            {sessionData.knowledge_missing_aspects?.length > 0 && (
              <div className={styles.debugRow}><span className={styles.debugLabel}>Missing:</span><span className={styles.debugVal}>{sessionData.knowledge_missing_aspects.join(", ")}</span></div>
            )}
          </div>
          
          <div className={styles.debugSection}>
            <div className={styles.debugTitle}>Report Status</div>
            <div className={styles.debugRow}><span className={styles.debugLabel}>Source:</span><span className={styles.debugVal}>{sessionData.report_source || "N/A"}</span></div>
            <div className={styles.debugRow}><span className={styles.debugLabel}>Flags:</span><span className={styles.debugVal}>{sessionData.report_quality_flags?.length || 0}</span></div>
          </div>
        </div>
      )}
    </div>
  );
}
