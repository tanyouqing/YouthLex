"use client";

import React, { useEffect, useState } from "react";
import { checkHealth } from "../../lib/api";
import { useTriageStream } from "../../hooks/useTriageStream";
import { useSessionRestore } from "../../hooks/useSessionRestore";
import { ThemeToggle } from "../../components/theme/ThemeToggle";
import { EmptyState } from "../../components/triage/EmptyState";
import { ProgressHeader } from "../../components/triage/ProgressHeader";
import { ChatPanel } from "../../components/triage/ChatPanel";
import { Sidebar } from "../../components/triage/Sidebar";
import { SCENARIO_OPTIONS } from "../../constants/triage";
import styles from "../../styles/triage.module.css";
import { 
  TriageScenario, 
  ConversationMessage, 
  StageProgress, 
  TriageSidebar, 
  FrontendGuidance,
  TriageResponse
} from "../../types/triage";

const WELCOME_MESSAGE = "遇到维权困难了？跟我讲讲，我来帮你解决";

function buildEmptySidebarData(): TriageSidebar {
  return {
    evidence_slots: {
      counterparty: null,
      time_place: null,
      amount: null,
      agreement: null,
      breach_fact: null,
      existing_evidence: [],
    },
    action_steps: [],
    demand_letter: null,
    similar_cases: [],
  };
}

function buildPreSessionGuidance(): FrontendGuidance {
  return {
    display_mode: "slot_collection",
    primary_panel: "evidence_slots",
    input_placeholder: "请详细描述你遇到的维权事件，我会基于你的情况继续帮你分析",
    follow_up_questions: [],
    suggested_actions: [],
  };
}

function findScenarioLabel(scenario: TriageScenario): string {
  return SCENARIO_OPTIONS.find((option) => option.value === scenario)?.label ?? "其他维权问题";
}

export default function TriagePage() {
  // Connection state
  const [isOnline, setIsOnline] = useState(true);
  
  // App states
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [scenario, setScenario] = useState<TriageScenario | null>(null);
  const [scenarioLabel, setScenarioLabel] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [progress, setProgress] = useState<StageProgress | null>(null);
  const [sidebarData, setSidebarData] = useState<TriageSidebar | null>(null);
  const [frontendData, setFrontendData] = useState<FrontendGuidance | null>(null);
  
  const [currentRunningStage, setCurrentRunningStage] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  
  const [availableSessionId, setAvailableSessionId] = useState<string | null>(() => {
    if (typeof window === "undefined") {
      return null;
    }
    return localStorage.getItem("triage_session_id");
  });

  // Hooks
  const { isStreaming, startStream } = useTriageStream();
  const { isRestoring, restoreSession } = useSessionRestore();

  // Initialization check
  useEffect(() => {
    checkHealth().then(online => setIsOnline(online));
  }, []);

  const handleResumeSession = () => {
    if (availableSessionId) {
      restoreSession(availableSessionId).then(res => {
        if (res) {
          applySnapshot(res);
        } else {
          setAvailableSessionId(null);
        }
      });
    }
  };

  const applySnapshot = (res: TriageResponse) => {
    setSessionId(res.session_id);
    setScenario(res.scenario);
    setScenarioLabel(res.scenario_label);
    setMessages(res.conversation_history);
    setProgress(res.progress);
    setSidebarData(res.sidebar);
    setFrontendData(res.frontend);
    setCurrentRunningStage(res.current_stage);
  };

  const handleSendMessage = (text: string) => {
    setErrorMsg(null);
    setMessages(prev => [...prev, { role: "user", content: text }]);

    const request =
      sessionId
        ? { user_input: text, session_id: sessionId, scenario: null, scenario_hint: null }
        : { user_input: text, session_id: null, scenario: null, scenario_hint: scenario };

    startStream(request, {
      onSession: (data) => {
        setSessionId(data.session_id);
        setScenario(data.scenario);
        setAvailableSessionId(data.session_id);
        localStorage.setItem("triage_session_id", data.session_id);
      },
      onStageStarted: (data) => {
        setCurrentRunningStage(data.stage);
      },
      onStageCompleted: (data) => {
        setProgress(data.progress);
        setFrontendData(data.frontend);
        setSidebarData(data.sidebar);
        setCurrentRunningStage(data.stage);
      },
      onComplete: (data) => {
        applySnapshot(data.response);
      },
      onError: (err) => {
        const msg = (err as Error).message || err.toString();
        setErrorMsg("请求中断：" + msg);
        setCurrentRunningStage(null);
      }
    });
  };

  const handleSelectScenario = (scen: TriageScenario) => {
    setSessionId(null);
    setScenario(scen);
    setScenarioLabel(findScenarioLabel(scen));
    setMessages([{ role: "assistant", content: WELCOME_MESSAGE }]);
    setProgress(null);
    setSidebarData(buildEmptySidebarData());
    setFrontendData(buildPreSessionGuidance());
    setCurrentRunningStage(null);
    setErrorMsg(null);
  };

  const handleResetSession = () => {
    if (sessionId) {
      localStorage.removeItem("triage_session_id");
      setAvailableSessionId(null);
    }
    setSessionId(null);
    setScenario(null);
    setScenarioLabel(null);
    setMessages([]);
    setProgress(null);
    setSidebarData(null);
    setFrontendData(null);
    setCurrentRunningStage(null);
    setErrorMsg(null);
  };

  if (isRestoring) {
    return <div className={styles.triageContainer} style={{alignItems: 'center', justifyContent: 'center', fontSize: 24}}>恢复历史进度中...</div>;
  }

  const inActiveSession = !!sessionId && messages.length > 0;
  const inPrimedSession = !sessionId && !!scenario && messages.length > 0;
  const showWorkbench = inActiveSession || inPrimedSession || isStreaming;

  return (
    <div className={styles.triageContainer}>

      <div style={{ position: 'absolute', top: 12, right: 12, zIndex: 100 }}>
        <ThemeToggle />
      </div>

      {!isOnline && (
        <div className={`${styles.bgRed}`} style={{ position: 'absolute', top: 60, left: 0, right: 0, padding: 8, textAlign: 'center', zIndex: 50, fontSize: 13, fontWeight: 'bold' }}>
          后端服务连接异常，请检查本地 8000 端口服务状态。
        </div>
      )}

      {errorMsg && (
        <div className={`${styles.bgYellow}`} style={{ position: 'absolute', top: 60, left: 0, right: 0, padding: 8, textAlign: 'center', zIndex: 50, fontSize: 13, fontWeight: 'bold', display: 'flex', justifyContent: 'center', gap: 16 }}>
          <span>{errorMsg}</span>
          <button style={{textDecoration: 'underline', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 'bold'}} onClick={() => setErrorMsg(null)}>关闭</button>
        </div>
      )}

      {!showWorkbench ? (
        <EmptyState 
          onSelectScenario={handleSelectScenario}
          hasPreviousSession={!!availableSessionId}
          onResumeSession={handleResumeSession}
        />
      ) : (
        <>
          <ProgressHeader 
            scenarioLabel={scenarioLabel}
            completedStages={progress?.completed_stages || []}
            currentStage={currentRunningStage || progress?.current_stage || null}
            evidenceRatio={progress?.evidence_completion_ratio || 0}
          />
          <div className={styles.mainArea}>
            <ChatPanel 
              messages={messages}
              loadingStage={isStreaming ? currentRunningStage : null}
              guidance={frontendData}
              onSendMessage={handleSendMessage}
            />
            <Sidebar 
              key={frontendData?.primary_panel || "evidence_slots"}
              sidebarData={sidebarData}
              primaryPanel={frontendData?.primary_panel || "evidence_slots"}
              mode={inPrimedSession ? "pre_session" : "default"}
            />
          </div>
          <button title="重新开始对话" className={`${styles.actionPill} ${styles.brutalShadow} ${styles.bgRed}`} style={{ position: 'absolute', bottom: 20, left: 20, zIndex: 100 }} onClick={handleResetSession}>
             清空会话 / 回到起始
          </button>
        </>
      )}
    </div>
  );
}
