import { CounterargumentStructured, CounterargumentCitations } from "../../types/api";
import styles from "../../styles/chat.module.css";

interface Props {
  structured: CounterargumentStructured;
  citations: CounterargumentCitations;
}

const SECTION_MAP: Array<{ key: keyof CounterargumentStructured; label: string }> = [
  { key: "claim_summary", label: "主张概括" },
  { key: "core_rebuttal", label: "反驳核心" },
  { key: "legal_basis", label: "法律依据" },
  { key: "case_strategy", label: "类案策略" },
  { key: "evidence_challenge", label: "证据排查" },
  { key: "logic_challenge", label: "逻辑漏洞" },
];

export function CounterargumentCard({ structured, citations }: Props) {
  return (
    <div className={styles.structCard}>
      {SECTION_MAP.map(({ key, label }) => {
        const content = structured[key];
        // Only render section if content exists and isn't empty array
        if (!content || (Array.isArray(content) && content.length === 0)) return null;

        const citeList = citations[key as keyof CounterargumentCitations] || [];

        return (
          <div key={key} className={styles.structSection}>
            <div className={styles.structTitle}>{label}</div>
            <div className={styles.structContent}>
              {Array.isArray(content) ? content.join(" / ") : content}
            </div>
            {citeList.length > 0 && (
               <div>
                 {citeList.map((cite, idx) => (
                   <span key={idx} className={styles.citation}>{cite}</span>
                 ))}
               </div>
            )}
          </div>
        );
      })}
      
      {/* Gap notes are usually arrays */}
      {structured.support_gap_notes && structured.support_gap_notes.length > 0 && (
        <div className={styles.structSection}>
          <div className={styles.structTitle}>补强缺口</div>
          <div className={styles.structContent}>
            {structured.support_gap_notes.map((note, i) => (
              <div key={i}>• {note}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
