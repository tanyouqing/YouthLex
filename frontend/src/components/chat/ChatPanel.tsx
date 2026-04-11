"use client";

import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import styles from "../../styles/chat.module.css";
import React from 'react';

export function ChatPanel() {
  return (
    <main className={styles.chatContainer}>
      <MessageList />
      <ChatInput />
    </main>
  );
}
