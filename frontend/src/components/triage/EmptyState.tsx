import React from "react";
import Link from "next/link";
import styles from "../../styles/triage.module.css";
import { SCENARIO_OPTIONS } from "../../constants/triage";
import { TriageScenario } from "../../types/triage";

interface EmptyStateProps {
  onSelectScenario: (scenario: TriageScenario) => void;
  hasPreviousSession?: boolean;
  onResumeSession?: () => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ onSelectScenario, hasPreviousSession, onResumeSession }) => {
  return (
    <div className={styles.emptyStateWrapper}>
      <div className={styles.emptyTopActions}>
        <Link href="/" className={`${styles.actionPill} ${styles.bgWhite} ${styles.headerHomeBtn}`}>
          🏠 返回主页
        </Link>
      </div>
      <div className={styles.heroBox}>
        <h1 className={styles.heroTitle}>
          青律 · 维权小助手
        </h1>
        <p className={styles.heroDescription}>
          先选择一个参考场景，进入对话后再详细描述你的维权事件。
        </p>
        {hasPreviousSession && (
          <div className={styles.resumeWrap}>
            <button 
              className={`${styles.actionPill} ${styles.bgPurple} ${styles.brutalShadow}`} 
              onClick={onResumeSession}
              style={{ fontSize: '16px', padding: '12px 24px' }}
            >
              🔄 恢复上一次的咨询进度
            </button>
          </div>
        )}
      </div>

      <div className={styles.scenarioGrid}>
        {SCENARIO_OPTIONS.map((opt) => (
          <div
            key={opt.value}
            className={`${styles.scenarioCard} ${styles.brutalShadow}`}
            onClick={() => onSelectScenario(opt.value as TriageScenario)}
          >
            <div className={styles.scenarioIcon}>{opt.icon}</div>
            <div className={styles.scenarioTitle}>{opt.label}</div>
            <div className={styles.scenarioExample}>
              &quot;{opt.example}&quot;
            </div>
            
            <button className={`${styles.actionPill} ${styles.bgWhite}`}>
              选择该场景
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
