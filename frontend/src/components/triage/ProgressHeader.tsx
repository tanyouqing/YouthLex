import React from "react";
import Link from "next/link";
import styles from "../../styles/triage.module.css";
import { STAGE_META } from "../../constants/triage";

interface ProgressHeaderProps {
  scenarioLabel: string | null;
  completedStages: string[];
  currentStage: string | null;
  evidenceRatio: number;
}

export const ProgressHeader: React.FC<ProgressHeaderProps> = ({
  scenarioLabel,
  completedStages,
  currentStage,
  evidenceRatio
}) => {
  const stageKeys = Object.keys(STAGE_META);

  return (
    <div className={styles.headerBox}>
      <div className={styles.headerLeft}>
        <Link href="/" className={`${styles.actionPill} ${styles.bgWhite} ${styles.headerHomeBtn}`}>
          🏠 返回主页
        </Link>
        <div className={`${styles.actionPill} ${styles.bgPurple} ${styles.scenarioBadge}`}>
          {scenarioLabel || "⚖️ 等待诊断..."}
        </div>
      </div>

      <div className={styles.stageTracker}>
        {stageKeys.map((key) => {
          const meta = STAGE_META[key];
          const isCompleted = completedStages.includes(key) && key !== currentStage;
          const isActive = key === currentStage;
          
          let dotClass = styles.pending;
          if (isCompleted) dotClass = styles.completed;
          if (isActive) dotClass = styles.active;

          return (
            <div key={key} className={styles.trackerItem}>
              <div
                className={`${styles.stageDot} ${dotClass}`}
                title={meta.label}
              >
                {meta.order}
              </div>
              <span className={styles.stageLabel}>
                {meta.label}
              </span>
              {meta.order < 5 && (
                <div className={styles.stageConnector}></div>
              )}
            </div>
          );
        })}
      </div>

      <div className={styles.evidenceBox}>
        <span className={styles.evidenceLabel}>证据收集度</span>
        <div className={styles.evidenceBar}>
          <div
            className={styles.evidenceFill}
            style={{
              width: `${evidenceRatio * 100}%`,
              borderRight: evidenceRatio > 0 ? '2px solid var(--border)' : 'none'
            }}
          />
        </div>
        <span className={styles.evidencePercent}>{Math.round(evidenceRatio * 100)}%</span>
      </div>
    </div>
  );
};
