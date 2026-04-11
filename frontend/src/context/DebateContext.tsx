"use client";

import React, { createContext, useContext, useReducer, useEffect } from "react";
import {
  SessionStateSummary,
  ErrorResponse,
  CounterargumentStructured,
  CounterargumentCitations,
} from "../types/api";

// ─── Types & State ──────────────────────────────────────────────

export interface ChatMessage {
  id: string; // Add stable ID
  role: "user" | "assistant";
  content: string;
  detail?: string;
  counterargumentStructured?: CounterargumentStructured;
  counterargumentCitations?: CounterargumentCitations;
  counterargumentQualityFlags?: string[];
  attackTargetCategory?: string | null;
  attackTargetSource?: string | null;
}

export interface DebateState {
  sessionId: string | null;
  sessionData: SessionStateSummary | null;
  messages: ChatMessage[];
  isLoading: boolean;
  draftText: string;
  detailOpenIndex: Set<number>;
  config: {
    caseBackground: string;
    scenarioHint: string;
    maxRounds: number;
  };
  error: ErrorResponse | null;
  backendHealthy: boolean | null;
}

// ─── Actions & Reducer ──────────────────────────────────────────

type Action =
  | { type: "SET_HEALTH"; payload: boolean }
  | { type: "SET_LOADING"; payload: boolean }
  | { type: "SET_CONFIG"; payload: Partial<DebateState["config"]> }
  | { type: "SET_DRAFT"; payload: string }
  | { type: "SET_ERROR"; payload: ErrorResponse | null }
  | { type: "TOGGLE_DETAIL"; payload: number }
  | { type: "INIT_SESSION"; payload: { sessionId: string; sessionData: SessionStateSummary } }
  | { type: "ADD_USER_MSG"; payload: { text: string } }
  | { type: "RESOLVE_TURN"; payload: SessionStateSummary } // Success response from turn
  | { type: "FAIL_TURN"; payload: ErrorResponse } // Failure removes optimistic user msg
  | { type: "RESTORE_SESSION"; payload: SessionStateSummary };

const generateId = () => Math.random().toString(36).substring(2, 9);

const initialState: DebateState = {
  sessionId: null,
  sessionData: null,
  messages: [],
  isLoading: false,
  draftText: "",
  detailOpenIndex: new Set(),
  config: {
    caseBackground: "学生租房退租后，房东拒绝返还押金并主张维修费用。",
    scenarioHint: "rental_dispute",
    maxRounds: 5,
  },
  error: null,
  backendHealthy: null,
};

function debateReducer(state: DebateState, action: Action): DebateState {
  switch (action.type) {
    case "SET_HEALTH":
      return { ...state, backendHealthy: action.payload };
    case "SET_LOADING":
      return { ...state, isLoading: action.payload };
    case "SET_CONFIG":
      return { ...state, config: { ...state.config, ...action.payload } };
    case "SET_DRAFT":
      return { ...state, draftText: action.payload };
    case "SET_ERROR":
      return { ...state, error: action.payload };
    case "TOGGLE_DETAIL": {
      const newSet = new Set(state.detailOpenIndex);
      if (newSet.has(action.payload)) newSet.delete(action.payload);
      else newSet.add(action.payload);
      return { ...state, detailOpenIndex: newSet };
    }
    case "INIT_SESSION":
      return {
        ...state,
        sessionId: action.payload.sessionId,
        sessionData: action.payload.sessionData,
        messages: [],
        draftText: "",
        error: null,
        detailOpenIndex: new Set(),
      };
    case "ADD_USER_MSG":
      if (!action.payload.text) return state;
      return {
        ...state,
        messages: [
          ...state.messages,
          { id: generateId(), role: "user", content: action.payload.text },
        ],
      };
    case "RESOLVE_TURN": {
      const data = action.payload;
      const newMessages = [...state.messages];
      
      // Only add agent message if there's actual content
      if (data.assistant_brief || data.assistant_detail) {
          newMessages.push({
            id: generateId(),
            role: "assistant",
            content: data.assistant_brief,
            detail: data.assistant_detail,
            counterargumentStructured: Object.keys(data.counterargument_structured).length ? data.counterargument_structured : undefined,
            counterargumentCitations: data.counterargument_citations,
            counterargumentQualityFlags: data.counterargument_quality_flags,
            attackTargetCategory: data.attack_target_category,
            attackTargetSource: data.attack_target_source
          });
      }

      return {
        ...state,
        sessionData: data,
        messages: newMessages,
        error: null,
        draftText: "", // Clear draft ONLY on success
      };
    }
    case "FAIL_TURN": {
       // If last message was user (optimistic), we should ideally leave it or mark it failed.
       // For this simple implementation, we keep the user message but show error.
       // The draft text is ALREADY preserved because RESOLVE_TURN clears it, not ADD_USER_MSG.
      return {
        ...state,
        error: action.payload
      };
    }
    case "RESTORE_SESSION":
      // Since history reconstruction requires backend state, and we don't have full chat history structured 
      // in the response root (only in `debate_history` which isn't cleanly in API), 
      // we'll just restore the config block and empty messages if missing.
      // In a real app we'd parse `state.debate_history`. We'll just reset messages for now on load 
      // or assume the user clears it.
      return {
        ...state,
        sessionId: action.payload.session_id,
        sessionData: action.payload,
        error: null
      };
    default:
      return state;
  }
}

// ─── Provider & Hook ────────────────────────────────────────────

interface DebateContextProps {
  state: DebateState;
  dispatch: React.Dispatch<Action>;
}

const DebateContext = createContext<DebateContextProps | undefined>(undefined);

export function DebateProvider({ children }: { children: React.ReactNode }) {
  const [state, dispatch] = useReducer(debateReducer, initialState);

  useEffect(() => {
    if (state.sessionId) {
      localStorage.setItem("debate_session_id", state.sessionId);
    }
  }, [state.sessionId]);

  return (
    <DebateContext.Provider value={{ state, dispatch }}>
      {children}
    </DebateContext.Provider>
  );
}

export function useDebateState() {
  const context = useContext(DebateContext);
  if (!context) throw new Error("useDebateState must be used within DebateProvider");
  return context;
}
