"use client";

import { useDebateState } from "../../context/DebateContext";
import { useDebate } from "../../hooks/useDebate";
import styles from "../../styles/chat.module.css";
import React from "react";

export function ChatInput() {
  const { state: { sessionData, isLoading, draftText, error } } = useDebateState();
  const { handleTurn, setDraft } = useDebate();

  const isSessionStarted = sessionData !== null;
  const isEnded = sessionData?.should_end || sessionData?.end_reason_code === "MAX_ROUNDS_REACHED";

  const onSend = () => {
    if (!draftText.trim()) return;
    handleTurn("send", draftText);
  };

  const onEnd = () => {
    handleTurn("end");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      onSend();
    }
  };

  return (
    <div className={styles.inputArea}>
      <div className={styles.inputWrapper}>
        <textarea
          className={styles.chatTextarea}
          placeholder={!isSessionStarted ? "请先在左侧新建会话..." : isEnded ? "会话已结束" : "输入您的主张或回复... (Cmd/Ctrl + Enter 发送)"}
          value={draftText}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={!isSessionStarted || isEnded || isLoading}
        />
        <div className={styles.btnGroup}>
          <button 
            className={`${styles.btnAction} ${styles.btnSend}`} 
            onClick={onSend}
            disabled={!isSessionStarted || isEnded || isLoading || !draftText.trim()}
          >
            发送 [SEND]
          </button>
          <button 
            className={styles.btnAction} 
            onClick={onEnd}
            disabled={!isSessionStarted || isEnded || isLoading}
          >
            结束辩论 [END]
          </button>
        </div>
      </div>
      
      {error && (
        <div style={{ color: "var(--error)", fontSize: "0.85rem", fontWeight: "bold" }}>
          故障: [{error.error.code}] {error.error.message}
          {error.trace_id && <span style={{display: 'block', fontSize: '0.7rem', color: 'var(--text-tertiary)'}}>TRACE: {error.trace_id}</span>}
        </div>
      )}
    </div>
  );
}
