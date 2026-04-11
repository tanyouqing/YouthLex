export type TriageScenario =
  | "housing"
  | "labor"
  | "consumer"
  | "debt"
  | "ip_reputation"
  | "other";

export interface EvidenceSlots {
  counterparty: string | null;
  time_place: string | null;
  amount: string | null;
  agreement: string | null;
  breach_fact: string | null;
  existing_evidence: string[];
}

export interface SimilarCase {
  title: string;
  summary: string;
  judgment: string;
  takeaway: string;
}

export interface TriageSidebar {
  evidence_slots: EvidenceSlots;
  action_steps: string[];
  demand_letter: string | null;
  similar_cases: SimilarCase[];
}

export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
  thinkingSteps?: { stage: string; content: string }[];
}

export interface AssistantTurn {
  role: "assistant";
  content: string;
  stage: string;
}

export interface StageProgress {
  current_stage: string;
  completed_stages: string[];
  remaining_stages: string[];
  next_stage: string | null;
  collected_slots: string[];
  missing_slots: string[];
  evidence_completion_ratio: number;
  evidence_complete: boolean;
  deliverables_ready: boolean;
}

export interface FrontendGuidance {
  display_mode: "slot_collection" | "action_guidance" | "deliverables_ready";
  primary_panel: "evidence_slots" | "action_steps" | "demand_letter";
  input_placeholder: string;
  follow_up_questions: string[];
  suggested_actions: string[];
}

export interface TriageResponse {
  session_id: string;
  scenario: TriageScenario;
  scenario_label: string;
  assistant_message: string;
  current_stage: string;
  assistant_turn: AssistantTurn;
  conversation_history: ConversationMessage[];
  progress: StageProgress;
  frontend: FrontendGuidance;
  sidebar: TriageSidebar;
}

export interface TriageRequest {
  user_input: string;
  scenario?: TriageScenario | null;
  scenario_hint?: TriageScenario | null;
  session_id?: string | null;
}

export type SSEEventType =
  | "session"
  | "stage_started"
  | "stage_completed"
  | "complete"
  | "error";

export interface SSESessionPayload {
  session_id: string;
  scenario: TriageScenario;
}

export interface SSEStageStartedPayload {
  stage: string;
  session_id: string;
}

export interface SSEStageCompletedPayload {
  stage: string;
  session_id: string;
  assistant_turn: AssistantTurn;
  progress: StageProgress;
  frontend: FrontendGuidance;
  sidebar: TriageSidebar;
}

export interface SSECompletePayload {
  response: TriageResponse;
}

export interface SSEErrorPayload {
  message: string;
  session_id: string;
}
