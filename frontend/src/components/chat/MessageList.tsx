"use client";

import { useDebateState } from "../../context/DebateContext";
import { UserBubble, AgentBubble } from "./Bubbles";
import { useAutoScroll } from "../../hooks/useAutoScroll";
import styles from "../../styles/chat.module.css";
import React from 'react';

export function MessageList() {
  const { state: { messages, detailOpenIndex, isLoading } } = useDebateState();
  const scrollRef = useAutoScroll([messages.length, detailOpenIndex]);

  return (
    <div className={styles.messageList} ref={scrollRef as React.RefObject<HTMLDivElement>}>
      {messages.length === 0 && (
        <div style={{ margin: "auto", color: "var(--text-tertiary)", fontFamily: "var(--font-mono)" }}>
          NO MESSAGES YET.<br />
          CONFIGURE AND INITIALIZE A NEW SESSION.
        </div>
      )}
      
      {messages.map((msg, idx) => {
        if (msg.role === "user") {
          return <UserBubble key={msg.id} message={msg} />;
        } else {
          return <AgentBubble key={msg.id} message={msg} index={idx} isOpen={detailOpenIndex.has(idx)} />;
        }
      })}

      {isLoading && (
        <div className={styles.agentMessageWrap}>
           <div className={styles.agentBubble} style={{ maxWidth: '100px' }}>
              <div className={styles.typingIndicator}>
                 <div className={styles.dot}></div>
                 <div className={styles.dot}></div>
                 <div className={styles.dot}></div>
              </div>
           </div>
        </div>
      )}
    </div>
  );
}
