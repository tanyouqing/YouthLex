"use client";

import { DebateProvider, useDebateState } from "../../context/DebateContext";
import { Sidebar } from "../../components/layout/Sidebar";
import { ChatPanel } from "../../components/chat/ChatPanel";
import { ReportPanel } from "../../components/report/ReportPanel";
import { DebugDrawer } from "../../components/debug/DebugDrawer";
import { ThemeToggle } from "../../components/theme/ThemeToggle";
import styles from "../../styles/layout.module.css";
import React from "react";

function Header() {
  const { state: { sessionData, backendHealthy } } = useDebateState();
  
  let hClass = styles.healthUnknown;
  let hText = "CHECKING BACKEND...";
  if (backendHealthy === true) {
    hClass = styles.healthOk;
    hText = "API CONNECTED";
  } else if (backendHealthy === false) {
    hClass = styles.healthErr;
    hText = "API OFFLINE";
  }

  const round = sessionData ? sessionData.round_index : 0;
  const max = sessionData ? sessionData.max_rounds : "-";

  return (
    <header className={styles.headerBar}>
      <div className={styles.title}>法律辩论陪练体系 / DEBATE AGENT v1.0</div>
      <div className={styles.stats}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className={`${styles.healthIndicator} ${hClass}`}></span>
          {hText}
        </div>
        <div style={{ borderLeft: "1px solid var(--border)", height: 20, margin: "0 8px" }}></div>
        <div>
          ROUND: {round} / {max}
        </div>
        <div style={{ borderLeft: "1px solid var(--border)", height: 20, margin: "0 8px" }}></div>
        <ThemeToggle />
      </div>
    </header>
  );
}

function MainLayout() {
  return (
    <div className={styles.container}>
      <Sidebar />
      <div className={styles.mainColumn}>
        <Header />
        <ChatPanel />
        <DebugDrawer />
      </div>
      <ReportPanel />
    </div>
  );
}

export default function DebateAppPage() {
  return (
    <DebateProvider>
      <MainLayout />
    </DebateProvider>
  );
}
