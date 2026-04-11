import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import styles from "../../styles/triage.module.css";
import { EvidenceSlots, TriageSidebar } from "../../types/triage";
import { SLOT_LABELS } from "../../constants/triage";

interface SidebarProps {
  sidebarData: TriageSidebar | null;
  primaryPanel: string;
  mode?: "default" | "pre_session";
}

export const Sidebar: React.FC<SidebarProps> = ({
  sidebarData,
  primaryPanel,
  mode = "default",
}) => {
  const [openPanels, setOpenPanels] = useState<Record<string, boolean>>({
    evidence_slots: primaryPanel === "evidence_slots" || !primaryPanel,
    action_steps: primaryPanel === "action_steps",
    demand_letter: primaryPanel === "demand_letter",
  });

  const togglePanel = (key: string) => {
    setOpenPanels(p => ({ ...p, [key]: !p[key] }));
  };

  const copyText = (text: string) => {
    try {
      navigator.clipboard.writeText(text);
      alert("复制成功");
    } catch {
      alert("复制失败");
    }
  };

  if (!sidebarData) {
    return <div className={styles.sidebar} style={{ alignItems: 'center', justifyContent: 'center' }}>数据加载中...</div>;
  }

  const { evidence_slots, action_steps, demand_letter, similar_cases } = sidebarData;
  const missingSlotsCount = Object.values(evidence_slots).filter(v => v === null || (Array.isArray(v) && v.length === 0)).length;
  const slotKeys: Array<keyof EvidenceSlots> = [
    "counterparty",
    "time_place",
    "amount",
    "agreement",
    "breach_fact",
    "existing_evidence",
  ];

  return (
    <div className={styles.sidebar}>
      
      {/* Evidence Panel */}
      <div className={styles.panelWrapper}>
        <div className={styles.panelHeader} onClick={() => togglePanel("evidence_slots")}>
          <span>📋 证据链补全 {missingSlotsCount === 0 ? "✅" : `(缺${missingSlotsCount})`}</span>
          <span>{openPanels.evidence_slots ? "▼" : "▶"}</span>
        </div>
        {openPanels.evidence_slots && (
          <div className={styles.panelContent}>
            <div className={styles.evidenceGrid}>
              {slotKeys.map((key) => {
                const label = SLOT_LABELS[key];
                const value = evidence_slots[key];
                const isMissing = value === null || (Array.isArray(value) && value.length === 0);
                
                return (
                  <div key={key} className={`${styles.evidenceSlot} ${isMissing ? styles.slotMissing : styles.bgGreen}`} style={isMissing ? {borderColor: '#FF3D00'} : {}}>
                    <span className={styles.slotLabel} style={isMissing ? {color: '#FF3D00'} : {}}>{label}</span>
                    <span className={styles.slotValue}>
                      {isMissing ? "待补充" : (Array.isArray(value) ? value.join('; ') : value)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Action Plan Panel */}
      <div className={styles.panelWrapper}>
        <div className={styles.panelHeader} onClick={() => togglePanel("action_steps")}>
          <span>🗺️ 维权步骤</span>
          <span>{openPanels.action_steps ? "▼" : "▶"}</span>
        </div>
        {openPanels.action_steps && (
          <div className={styles.panelContent}>
            {action_steps && action_steps.length > 0 ? (
              <>
                <ol style={{ paddingLeft: '20px', marginBottom: '16px' }}>
                  {action_steps.map((step, idx) => (
                    <li key={idx} style={{ marginBottom: '8px' }}>{step}</li>
                  ))}
                </ol>
                <button 
                  className={`${styles.actionPill} ${styles.bgWhite}`} 
                  onClick={() => copyText(action_steps.join('\n'))}
                >
                  一键复制所有步骤
                </button>
              </>
            ) : (
              <div style={{ color: 'var(--text-secondary)' }}>
                {mode === "pre_session" ? "等待你描述事件后开始整理。" : "分析过程中动态生成指导步骤..."}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Deliverable Panel */}
      <div className={styles.panelWrapper}>
        <div className={styles.panelHeader} onClick={() => togglePanel("demand_letter")}>
          <span>📄 交付产物</span>
          <span>{openPanels.demand_letter ? "▼" : "▶"}</span>
        </div>
        {openPanels.demand_letter && (
          <div className={styles.panelContent} style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            
            {/* Demand Letter */}
            <div>
              <h4 style={{ marginBottom: '12px', fontSize: '15px' }}>催告函</h4>
              {demand_letter ? (
                <>
                  <div className={styles.markdownBox} style={{ maxHeight: '300px', overflowY: 'auto', marginBottom: '12px' }}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{demand_letter}</ReactMarkdown>
                  </div>
                  <button className={`${styles.actionPill} ${styles.bgYellow}`} onClick={() => copyText(demand_letter)}>
                    复制催告函
                  </button>
                </>
              ) : (
                <div style={{ color: 'var(--text-secondary)' }}>
                  {mode === "pre_session" ? "描述事件后生成催告函。" : "催告函将在分析完成后生成。"}
                </div>
              )}
            </div>

            {/* Similar Cases */}
            <div>
              <h4 style={{ marginBottom: '12px', fontSize: '15px' }}>相似案例</h4>
              {similar_cases && similar_cases.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {similar_cases.map((sc, idx) => (
                    <div key={idx} className={styles.markdownBox}>
                      <h5 style={{ borderBottom: '1px solid var(--border)', paddingBottom: '8px', marginBottom: '8px' }}>{sc.title}</h5>
                      <div style={{ fontSize: '13px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <div><strong>【摘要】</strong> {sc.summary}</div>
                        <div><strong>【结果】</strong> {sc.judgment}</div>
                        <div style={{ color: '#D500F9' }}><strong>【启示】</strong> {sc.takeaway}</div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ color: 'var(--text-secondary)' }}>
                  {mode === "pre_session" ? "描述事件后生成相似案例。" : "相似案例将结合法规自动匹配。"}
                </div>
              )}
            </div>
            
          </div>
        )}
      </div>

    </div>
  );
};
