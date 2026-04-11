"use client";

import { ChatMessage } from "../../context/DebateContext";
import { useDebate } from "../../hooks/useDebate";
import styles from "../../styles/chat.module.css";
import React from 'react';

const FormattedDetail = ({ text }: { text: string }) => {
  const parts = text.split(/(【.*?】)/g);
  return (
    <>
      {parts.map((part, i) => {
        if (part.startsWith('【') && part.endsWith('】')) {
          // 浅蓝色高亮标签
          return <span key={i} style={{ color: "#60a5fa", fontWeight: "bold" }}>{part}</span>;
        }
        return part;
      })}
    </>
  );
};

export function UserBubble({ message }: { message: ChatMessage }) {
  return (
    <div className={styles.userMessageWrap}>
      <div className={styles.userBubble}>
        <div className={styles.agentRole} style={{ color: "var(--bg-primary)" }}>USER / PLAINTIFF</div>
        <div style={{ whiteSpace: "pre-wrap", marginTop: 8 }}>{message.content}</div>
      </div>
    </div>
  );
}

export function AgentBubble({ message, index, isOpen }: { message: ChatMessage, index: number, isOpen: boolean }) {
  const { toggleDetail } = useDebate();
  
  const hasDetail = !!message.detail;
  const showFlags = message.counterargumentQualityFlags && message.counterargumentQualityFlags.length > 0;

  // 清除简要回复中的特定标签
  const displayContent = message.content ? message.content.replace(/【核心反驳】|【进一步追问】/g, "").trim() : "";

  return (
    <div className={styles.agentMessageWrap}>
      <div className={styles.agentBubble}>
        <div className={styles.agentHeader}>
          <div className={styles.agentRole}>AGENT / DEFENDANT</div>
          {hasDetail && (
            <button className={styles.detailBtn} onClick={() => toggleDetail(index)}>
              {isOpen ? "收起 [-]" : "详情 [+]"}
            </button>
          )}
        </div>
        
        {/* Quality Flags Warning */}
        {showFlags && (
          <div style={{ padding: "4px 8px", background: "var(--warning)", color: "#000", fontSize: "0.75rem", marginBottom: 8, fontWeight: "bold" }}>
             WARN: {message.counterargumentQualityFlags?.join(", ")}
          </div>
        )}

        <div style={{ whiteSpace: "pre-wrap" }}>{displayContent}</div>
        
        {/* Detail Drawer */}
        {isOpen && hasDetail && (
          <div className={styles.drawerContent}>
            <div style={{ whiteSpace: "pre-wrap", color: "var(--text-secondary)", lineHeight: 1.6 }}>
              <FormattedDetail text={message.detail || ""} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
