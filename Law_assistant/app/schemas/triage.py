from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class TriageScenario(str, Enum):
    HOUSING = "housing"
    LABOR = "labor"
    CONSUMER = "consumer"
    DEBT = "debt"
    IP_REPUTATION = "ip_reputation"
    OTHER = "other"


class EvidenceSlotsModel(BaseModel):
    counterparty: str | None = None
    time_place: str | None = None
    amount: str | None = None
    agreement: str | None = None
    breach_fact: str | None = None
    existing_evidence: list[str] = Field(default_factory=list)


class SimilarCaseModel(BaseModel):
    title: str
    summary: str
    judgment: str
    takeaway: str


class TriageSidebar(BaseModel):
    evidence_slots: EvidenceSlotsModel
    action_steps: list[str] = Field(default_factory=list)
    demand_letter: str | None = None
    similar_cases: list[SimilarCaseModel] = Field(default_factory=list)


class ConversationMessageModel(BaseModel):
    role: Literal["user", "assistant"] = Field(description="消息角色")
    content: str = Field(description="消息内容")


class AssistantTurnModel(BaseModel):
    role: Literal["assistant"] = Field(default="assistant", description="助手消息角色")
    content: str = Field(description="本轮助手回复")
    stage: str = Field(description="本轮回复对应的图阶段")


class StageProgressModel(BaseModel):
    current_stage: str = Field(description="当前流程阶段")
    completed_stages: list[str] = Field(default_factory=list, description="已完成阶段")
    remaining_stages: list[str] = Field(default_factory=list, description="待完成阶段")
    next_stage: str | None = Field(default=None, description="下一阶段")
    collected_slots: list[str] = Field(default_factory=list, description="已补齐证据槽位")
    missing_slots: list[str] = Field(default_factory=list, description="缺失证据槽位")
    evidence_completion_ratio: float = Field(description="证据槽位完成度，范围 0 到 1")
    evidence_complete: bool = Field(description="证据是否已补齐")
    deliverables_ready: bool = Field(description="催告函和相似案例是否已可展示")


class FrontendGuidanceModel(BaseModel):
    display_mode: str = Field(description="前端当前建议展示模式")
    primary_panel: str = Field(description="当前优先展开的侧边栏区域")
    input_placeholder: str = Field(description="输入框占位提示")
    follow_up_questions: list[str] = Field(default_factory=list, description="建议追问列表")
    suggested_actions: list[str] = Field(default_factory=list, description="前端可展示的快捷动作")


class TriageRequest(BaseModel):
    user_input: str = Field(min_length=1, description="用户当前输入")
    scenario: TriageScenario | None = Field(
        default=None, description="纠纷场景；为空时默认路由到 other"
    )
    scenario_hint: TriageScenario | None = Field(
        default=None,
        description="场景参考提示；仅用于首轮真实案情输入时辅助路由",
    )
    session_id: str | None = Field(default=None, description="会话 ID")


class TriageResponse(BaseModel):
    session_id: str
    scenario: TriageScenario
    scenario_label: str
    assistant_message: str
    current_stage: str
    assistant_turn: AssistantTurnModel
    conversation_history: list[ConversationMessageModel] = Field(default_factory=list)
    progress: StageProgressModel
    frontend: FrontendGuidanceModel
    sidebar: TriageSidebar
