"use client";

import { useDebateState } from "../../context/DebateContext";
import styles from "../../styles/report.module.css";
import React from 'react';

export function ReportPanel() {
  const { state: { sessionData } } = useDebateState();

  const report = sessionData?.report;
  
  if (!report) {
    return (
      <aside className={styles.reportContainer}>
        <div className={styles.emptyState}>
          <div>[ AWAITING REPORT ]</div>
          <p style={{ marginTop: 16 }}>对话结束后将在<br/>此生成辩论综合测算报告</p>
        </div>
      </aside>
    );
  }

  // Determine score color
  let scoreColor = "var(--score-mid)";
  if (report.overall_score >= 80) scoreColor = "var(--score-high)";
  if (report.overall_score < 60) scoreColor = "var(--score-low)";

  return (
    <aside className={styles.reportContainer}>
      <div className={styles.reportContent}>
        <h2 className={styles.header}>综合评测报告</h2>
        
        <div className={styles.scoreBanner}>
          <div className={styles.scoreLabel}>综合得分<br/>(OVERALL SCORE)</div>
          <div className={styles.scoreValue} style={{ color: scoreColor }}>{report.overall_score}</div>
        </div>

        <div className={styles.section}>
          <div className={styles.sectionTitle}>辩论背景</div>
          <div style={{ fontSize: "0.9rem" }}>{report.debate_background}</div>
        </div>

        <div className={styles.section}>
          <div className={styles.sectionTitle}>你方核心主张</div>
          <ul className={styles.list}>
            {report.user_claim_summary.map((item, i) => <li key={i} className={styles.listItem}>{item}</li>)}
          </ul>
        </div>

        <div className={styles.section}>
          <div className={styles.sectionTitle}>反方反驳核心</div>
          <ul className={styles.list}>
            {report.defendant_rebuttal_points.map((item, i) => <li key={i} className={styles.listItem}>{item}</li>)}
          </ul>
        </div>

        <div className={styles.section}>
          <div className={styles.sectionTitle}>表现优势 (STRENGTHS)</div>
          <ul className={styles.list}>
            {report.user_strengths.map((item, i) => <li key={i} className={styles.listItem}>{item}</li>)}
          </ul>
        </div>

        <div className={styles.section}>
          <div className={styles.sectionTitle}>失分漏洞 (WEAKNESSES)</div>
          <ul className={styles.list}>
            {report.user_weaknesses.map((item, i) => <li key={i} className={styles.listItem}>{item}</li>)}
          </ul>
        </div>

        <div className={styles.section}>
          <div className={styles.sectionTitle}>举证建议</div>
          <ul className={styles.list}>
            {report.evidence_improvement_suggestions.map((item, i) => <li key={i} className={styles.listItem}>{item}</li>)}
          </ul>
        </div>

        <div className={styles.section}>
          <div className={styles.sectionTitle}>法条适用建议</div>
          <ul className={styles.list}>
            {report.legal_argument_suggestions.map((item, i) => <li key={i} className={styles.listItem}>{item}</li>)}
          </ul>
        </div>
      </div>
      
      <div className={styles.footer}>
        <div>END REASON: {report.end_reason}</div>
        <div>SOURCE: {sessionData.report_source || "N/A"}</div>
        {sessionData.report_quality_flags && sessionData.report_quality_flags.length > 0 && (
           <div style={{ color: "var(--warning)", marginTop: "4px" }}>
             FLAGS: {sessionData.report_quality_flags.join(", ")}
           </div>
        )}
      </div>
    </aside>
  );
}
