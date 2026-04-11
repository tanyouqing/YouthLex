import React, { useRef, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import styles from "../../styles/triage.module.css";
import { ConversationMessage, FrontendGuidance } from "../../types/triage";

interface ChatPanelProps {
  messages: ConversationMessage[];
  loadingStage: string | null;
  guidance: FrontendGuidance | null;
  onSendMessage: (msg: string) => void;
}

const ThinkingDrawer = ({ steps }: { steps: {stage: string; content: string}[] }) => {
  const [isOpen, setIsOpen] = useState(false);
  
  if (!steps || steps.length === 0) return null;
  return (
    <div style={{ marginBottom: '12px', fontSize: '13px', background: 'var(--bg-tertiary)', border: '2px solid var(--border)' }}>
      <button 
        onClick={() => setIsOpen(!isOpen)}
        style={{ width: '100%', textAlign: 'left', padding: '8px 12px', cursor: 'pointer', background: 'transparent', border: 'none', color: 'var(--text-secondary)', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}
      >
        <span style={{ fontSize: '10px' }}>{isOpen ? "▼" : "▶"}</span>
        <span>🤔 分析与提取过程中 ({steps.length} 步) - 点击{isOpen ? "折叠" : "展开"}</span>
      </button>
      
      {isOpen && (
        <div style={{ padding: '8px 12px', borderTop: '2px dashed var(--border)', borderLeft: '4px solid #00E676', display: 'flex', flexDirection: 'column', gap: '12px', background: 'var(--bg-primary)' }}>
          {steps.map((s, i) => (
            <div key={i}>
              <div style={{ fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '4px', color: 'var(--text-secondary)' }}>[{s.stage}]</div>
              <div style={{ color: 'var(--text-primary)' }}><ReactMarkdown remarkPlugins={[remarkGfm]}>{s.content}</ReactMarkdown></div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export const ChatPanel: React.FC<ChatPanelProps> = ({
  messages,
  loadingStage,
  guidance,
  onSendMessage,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [inputVal, setInputVal] = React.useState("");

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loadingStage]);

  const handleSend = () => {
    if (!inputVal.trim() || loadingStage) return;
    onSendMessage(inputVal.trim());
    setInputVal("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className={styles.chatPanel}>
      {/* 消息列表 */}
      <div className={styles.messagesList} ref={scrollRef}>
        {messages.map((msg, idx) => (
          <div key={idx} className={`${styles.messageRow} ${msg.role === 'user' ? styles.user : styles.assistant}`}>
            {msg.role !== 'user' && (
              <div className={`${styles.avatarBox} ${styles.assistantAvatar}`} title="青律维权助手">👨‍⚖️</div>
            )}
            
            <div className={styles.bubble}>
              {msg.role === 'user' ? (
                <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
              ) : (
                <>
                  {msg.thinkingSteps && msg.thinkingSteps.length > 0 && <ThinkingDrawer steps={msg.thinkingSteps} />}
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {msg.content}
                  </ReactMarkdown>
                </>
              )}
            </div>

            {msg.role === 'user' && (
              <div className={`${styles.avatarBox} ${styles.userAvatar}`} title="当事人">🙎‍♂️</div>
            )}
          </div>
        ))}
        {loadingStage && (
          <div className={`${styles.messageRow} ${styles.assistant}`}>
            <div className={`${styles.avatarBox} ${styles.assistantAvatar}`} title="青律维权助手">👨‍⚖️</div>
            <div className={styles.bubble} style={{ opacity: 0.8 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className={styles.active} style={{ width: 10, height: 10, borderRadius: '50%', display: 'inline-block' }}></span>
                ⚖️ {loadingStage}...
              </span>
            </div>
          </div>
        )}
      </div>

      {/* 快捷按钮与输入框 */}
      <div className={styles.chatInputWrapper}>
        {guidance?.follow_up_questions && guidance.follow_up_questions.length > 0 && (
          <div className={styles.quickActions} style={{ flexDirection: 'column', alignItems: 'stretch', gap: '8px' }}>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)', fontWeight: 'bold' }}>
              本轮请优先回答这一项
            </div>
            {guidance.follow_up_questions.map((q, idx) => (
              <button
                key={idx}
                className={styles.actionPill}
                disabled={!!loadingStage}
                style={{ textAlign: 'left', whiteSpace: 'normal', lineHeight: 1.5 }}
                onClick={() => textareaRef.current?.focus()}
              >
                {q}
              </button>
            ))}
          </div>
        )}
        
        <div className={styles.inputRow}>
          <textarea
            ref={textareaRef}
            className={styles.textarea}
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={guidance?.input_placeholder || "请描述您遇到的问题..."}
            disabled={!!loadingStage}
          />
          <button
            className={`${styles.sendBtn} ${styles.brutalShadow}`}
            onClick={handleSend}
            disabled={!inputVal.trim() || !!loadingStage}
          >
            发送
          </button>
        </div>
      </div>
    </div>
  );
};
