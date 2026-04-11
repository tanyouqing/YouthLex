// ─── 枚举 / 字面量 ─────────────────────────────────

export type TurnAction = "send" | "end";
export type EndReasonCode = "IN_PROGRESS" | "USER_ENDED" | "MAX_ROUNDS_REACHED";
export type AttackTargetCategory =
  | "法律依据不足"
  | "证据链薄弱"
  | "因果链不完整"
  | "损失计算不充分"
  | "规则适用错误"
  | "程序或主体适格瑕疵"
  | "论点信息不足";
export type AttackTargetSource = "llm" | "fallback" | "reranked";
export type RetrievalMode = "vector" | "keyword_fallback";
export type ReportSource = "llm" | "fallback";

export const SCENARIO_OPTIONS = [
  { value: "rental_dispute", label: "租房纠纷" },
  { value: "part_time_wage", label: "兼职薪酬" },
  { value: "campus_loan", label: "校园贷" },
  { value: "training_refund", label: "培训退费" },
  { value: "student_rights", label: "学生权益" },
] as const;

// ─── 请求 ─────────────────────────────────────────

export interface CreateSessionRequest {
  case_background?: string;   // max 4000 chars
  scenario_hint?: string;     // max 128 chars
  max_rounds?: number;        // 1~20, default 5
}

export interface TurnRequest {
  action: TurnAction;
  user_text?: string;         // max 4000 chars; send 时必填非空, end 时可空
}

// ─── 响应：核心模型 ───────────────────────────────

export interface CounterargumentStructured {
  claim_summary?: string;
  core_rebuttal?: string;
  legal_basis?: string;
  case_strategy?: string;
  evidence_challenge?: string;
  logic_challenge?: string;
  support_gap_notes?: string[];
}

export interface CounterargumentCitations {
  claim_summary?: string[];
  core_rebuttal?: string[];
  legal_basis?: string[];
  case_strategy?: string[];
  evidence_challenge?: string[];
  logic_challenge?: string[];
}

export interface DebateReport {
  debate_background: string;
  user_claim_summary: string[];
  defendant_rebuttal_points: string[];
  user_strengths: string[];
  user_weaknesses: string[];
  evidence_improvement_suggestions: string[];
  legal_argument_suggestions: string[];
  overall_score: number;        // 0~100
  end_reason: string;
}

export interface SessionStateSummary {
  session_id: string;
  case_background: string;
  scenario_hint: string;
  max_rounds: number;
  round_index: number;
  ui_action: TurnAction;
  should_end: boolean;
  end_reason: string;
  end_reason_code: EndReasonCode;
  assistant_brief: string;
  assistant_detail: string;
  attack_target: string;
  attack_target_category: AttackTargetCategory | string | null;
  attack_target_reason: string;
  attack_target_source: AttackTargetSource | null;
  retrieval_mode: RetrievalMode | null;
  knowledge_sufficiency: boolean;
  knowledge_missing_aspects: string[];
  counterargument_structured: CounterargumentStructured;
  counterargument_citations: CounterargumentCitations;
  counterargument_quality_flags: string[];
  report_source: ReportSource | null;
  report_quality_flags: string[];
  history_count: number;
  updated_at: string;           // ISO 8601
  report: DebateReport | null;
}

export interface SessionEnvelope {
  session: SessionStateSummary;
}

// ─── 响应：错误 ───────────────────────────────────

export interface ErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ErrorResponse {
  error: ErrorBody;
  trace_id: string;
}

// ─── 响应：健康检查 ───────────────────────────────

export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
  timestamp: string;
}
