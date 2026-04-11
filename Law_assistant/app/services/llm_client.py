import json
import logging
import re
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, model_validator

from app.core.config import Settings, get_settings
from app.graphs.legal_triage.state import EvidenceSlots, ScenarioValue
from app.services.retrieval_types import LegalBasisItem, SimilarCaseItem


class LLMInvocationError(RuntimeError):
    """Raised when the model response cannot be parsed as expected."""


class EmpathyOutput(BaseModel):
    assistant_message: str = Field(description="用于安抚用户情绪的回复")


class LegalGroundingOutput(BaseModel):
    assistant_message: str = Field(description="法律定性说明")
    legal_basis_notes: list[str] = Field(default_factory=list, description="法规依据要点摘要")


class SlotFillingOutput(BaseModel):
    assistant_message: str = Field(description="引导用户补充信息的问题")
    missing_slots: list[str] = Field(default_factory=list, description="缺失槽位")


class EvidenceNormalizationOutput(BaseModel):
    counterparty: str | None = Field(default=None, description="标准化后的相对方信息")
    time_place: str | None = Field(default=None, description="标准化后的时间地点")
    amount: str | None = Field(default=None, description="标准化后的金额信息")
    agreement: str | None = Field(default=None, description="标准化后的约定信息")
    breach_fact: str | None = Field(default=None, description="标准化后的违约或侵权事实")
    existing_evidence: list[str] = Field(default_factory=list, description="标准化后的证据列表")


class ActionPlanOutput(BaseModel):
    assistant_message: str = Field(description="阶段说明")
    action_steps: list[str] = Field(default_factory=list, description="维权行动步骤")


class SimilarCaseOutput(BaseModel):
    title: str
    summary: str
    judgment: str
    takeaway: str

    @model_validator(mode="before")
    @classmethod
    def normalize_case(cls, value):
        if isinstance(value, str):
            return {
                "title": "示例案例",
                "summary": value,
                "judgment": "待接入真实案例库。",
                "takeaway": "可作为后续案例检索与维权论证的参考线索。",
            }
        return value


class DeliverablesOutput(BaseModel):
    assistant_message: str = Field(description="最终对用户的总结性回复")
    demand_letter: str = Field(description="维权说明函或催告函")
    similar_cases: list[SimilarCaseOutput] = Field(
        default_factory=list, description="相似案例列表"
    )


logger = logging.getLogger(__name__)


class LegalTriageLLM:
    def __init__(self, chat_model: ChatOpenAI):
        self._chat_model = chat_model

    def generate_empathy(self, user_input: str, scenario: ScenarioValue) -> EmpathyOutput:
        return self._invoke_json(
            system_prompt=(
                "你是“青律”高校维权助手。"
                "你的任务是先接住用户情绪，用温和、坚定、可信的中文回复。"
                "不要输出 JSON 以外的内容。"
            ),
            human_prompt=(
                f"纠纷场景：{scenario}\n"
                f"用户原话：{user_input}\n"
                "请输出 JSON，字段只有 assistant_message。"
            ),
            schema=EmpathyOutput,
        )

    def generate_legal_grounding(
        self,
        user_input: str,
        scenario: ScenarioValue,
        legal_basis_items: list[LegalBasisItem],
        retrieval_status: str,
    ) -> LegalGroundingOutput:
        return self._invoke_json(
            system_prompt=(
                "你是“青律”高校维权助手。"
                "请基于用户描述和给定的法规检索结果做初步法律定性，并给出 1 到 3 条法律依据要点。"
                "只能引用输入中明确给出的法规标题、发布机关、摘要信息。"
                "如果法规检索为空或失败，必须明确说明“暂未检索到足够法律依据”或“检索暂不可用”，"
                "并使用谨慎表述，不要编造具体条文编号、法院结论或确定性过强的法律判断。"
                "不要输出 JSON 以外的内容。"
            ),
            human_prompt=(
                f"纠纷场景：{scenario}\n"
                f"用户原话：{user_input}\n"
                f"检索状态：{retrieval_status}\n"
                f"法规检索结果：{json.dumps(legal_basis_items, ensure_ascii=False)}\n"
                "请输出 JSON，包含 assistant_message 和 legal_basis_notes。"
            ),
            schema=LegalGroundingOutput,
        )

    def generate_slot_filling(
        self,
        user_input: str,
        scenario: ScenarioValue,
        evidence_slots: EvidenceSlots,
        missing_slots: list[str],
    ) -> SlotFillingOutput:
        return self._invoke_json(
            system_prompt=(
                "你是“青律”高校维权助手。"
                "你需要根据“纠纷六要素”检查信息缺口，并向用户提出最多 3 个高价值补充问题。"
                "六要素固定为：counterparty, time_place, amount, agreement, breach_fact, existing_evidence。"
                "只输出仍然缺失的字段。"
                "如果六要素已经基本完整，请明确说明“信息已基本完整”，并把 missing_slots 返回为空数组。"
                "不要输出 JSON 以外的内容。"
            ),
            human_prompt=(
                f"纠纷场景：{scenario}\n"
                f"用户原话：{user_input}\n"
                f"当前证据槽位：{json.dumps(evidence_slots, ensure_ascii=False)}\n"
                f"当前缺失槽位：{json.dumps(missing_slots, ensure_ascii=False)}\n"
                "请输出 JSON，包含 assistant_message 和 missing_slots。"
            ),
            schema=SlotFillingOutput,
        )

    def normalize_evidence_slots(
        self,
        user_input: str,
        scenario: ScenarioValue,
        current_slots: EvidenceSlots,
        rule_extracted_slots: EvidenceSlots,
        requested_slot: str | None = None,
    ) -> EvidenceNormalizationOutput:
        return self._invoke_json(
            system_prompt=(
                "你是“青律”高校维权助手中的证据整理模块。"
                "你的任务是把用户这一轮的口语化表达，整理成纠纷六要素里的结构化槽位。"
                "六要素固定为：counterparty, time_place, amount, agreement, breach_fact, existing_evidence。"
                "请只提炼用户当前这一轮明确说出的信息，不要编造。"
                "允许保留不确定性，例如“约30余元”“总额待进一步核算”“时间：昨天晚上”“地点：学校北门阿慧面馆”。"
                "如果这一轮没有提供对应信息，请返回 null 或空数组。"
                "amount 可以整理为多段字符串，例如“餐费16元；检查费约300余元；总额待进一步核算”。"
                "time_place 若同时有时间和地点，请输出“时间：...；地点：...”格式；只有一项时只输出那一项。"
                "existing_evidence 只返回证据名数组，例如“聊天记录”“转账记录”“消费小票”“现场视频”。"
                "不要输出 JSON 以外的内容。"
            ),
            human_prompt=(
                f"纠纷场景：{scenario}\n"
                f"当前追问槽位：{requested_slot or '无'}\n"
                f"用户本轮原话：{user_input}\n"
                f"当前已收集槽位：{json.dumps(current_slots, ensure_ascii=False)}\n"
                f"规则抽取结果：{json.dumps(rule_extracted_slots, ensure_ascii=False)}\n"
                "请输出 JSON，包含 counterparty、time_place、amount、agreement、breach_fact、existing_evidence。"
            ),
            schema=EvidenceNormalizationOutput,
        )

    def generate_action_plan(
        self,
        user_input: str,
        scenario: ScenarioValue,
        evidence_slots: EvidenceSlots,
        missing_slots: list[str],
        legal_basis_notes: list[str],
        suggested_steps: list[str],
    ) -> ActionPlanOutput:
        return self._invoke_json(
            system_prompt=(
                "你是“青律”高校维权助手。"
                "请输出按时间顺序排列、具备实操性的维权步骤。"
                "步骤要尽量结合纠纷场景、现有证据完整度和已经检索到的法律依据摘要。"
                "优先说明先做什么、再做什么、需要联系哪类平台或部门。"
                "不要捏造具体平台规则或精确办案机关名称；如果需要，可使用“当地劳动监察部门”“平台客服/举报入口”等稳妥表达。"
                "不要输出 JSON 以外的内容。"
            ),
            human_prompt=(
                f"纠纷场景：{scenario}\n"
                f"用户原话：{user_input}\n"
                f"当前证据槽位：{json.dumps(evidence_slots, ensure_ascii=False)}\n"
                f"当前缺失槽位：{json.dumps(missing_slots, ensure_ascii=False)}\n"
                f"法规依据摘要：{json.dumps(legal_basis_notes, ensure_ascii=False)}\n"
                f"建议基础步骤：{json.dumps(suggested_steps, ensure_ascii=False)}\n"
                "请输出 JSON，包含 assistant_message 和 action_steps。"
            ),
            schema=ActionPlanOutput,
        )

    def generate_deliverables(
        self,
        user_input: str,
        scenario: ScenarioValue,
        action_steps: list[str],
        legal_basis_items: list[LegalBasisItem],
        legal_basis_notes: list[str],
        similar_case_items: list[SimilarCaseItem],
        retrieval_status: str,
        evidence_slots: EvidenceSlots,
        draft_demand_letter: str,
    ) -> DeliverablesOutput:
        return self._invoke_json(
            system_prompt=(
                "你是“青律”高校维权助手。"
                "请基于当前信息生成："
                "1. 一段给用户的总结性回复；"
                "2. 一份简洁、严肃的 Markdown 催告函；"
                "3. 1 到 2 个“相似案例”列表。"
                "催告函应优先参考输入里提供的草稿模板，不要随意改变已明确的事实、诉求和结构。"
                "优先使用输入中提供的真实类案信息，不要虚构真实法院案号、新闻来源或具体判决书编号。"
                "如果类案检索为空或失败，必须明确写“示例案例/待后续接入案例库”或“暂未检索到足够相似案例”。"
                "similar_cases 必须是对象数组，每个对象必须包含 title、summary、judgment、takeaway 四个字段。"
                "不要输出 JSON 以外的内容。"
            ),
            human_prompt=(
                f"纠纷场景：{scenario}\n"
                f"用户原话：{user_input}\n"
                f"当前证据槽位：{json.dumps(evidence_slots, ensure_ascii=False)}\n"
                f"法规检索结果：{json.dumps(legal_basis_items, ensure_ascii=False)}\n"
                f"法规依据摘要：{json.dumps(legal_basis_notes, ensure_ascii=False)}\n"
                f"行动步骤：{json.dumps(action_steps, ensure_ascii=False)}\n"
                f"类案检索状态：{retrieval_status}\n"
                f"类案检索结果：{json.dumps(similar_case_items, ensure_ascii=False)}\n"
                f"催告函草稿：{draft_demand_letter}\n"
                "请输出 JSON，包含 assistant_message、demand_letter、similar_cases。"
            ),
            schema=DeliverablesOutput,
        )

    def _invoke_json(self, system_prompt: str, human_prompt: str, schema: type[BaseModel]):
        response = self._chat_model.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=human_prompt)]
        )
        content = self._coerce_content_to_text(response.content)
        payload = self._extract_json_payload(content)

        try:
            return schema.model_validate(payload)
        except Exception as exc:  # pragma: no cover - defensive branch
            raise LLMInvocationError(f"MiniMax 返回结构不符合预期: {content}") from exc

    @staticmethod
    def _coerce_content_to_text(content: object) -> str:
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(str(item.get("text", "")))
                else:
                    text_parts.append(str(item))
            return "\n".join(part for part in text_parts if part).strip()

        return str(content).strip()

    @staticmethod
    def _extract_json_payload(content: str) -> dict:
        stripped = content.strip()

        code_block_pattern = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
        code_block_candidates = [
            match.group(1).strip() for match in code_block_pattern.finditer(stripped)
        ]

        for candidate in reversed(code_block_candidates):
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("{")
            end = stripped.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise LLMInvocationError(f"MiniMax 未返回可解析 JSON: {content}")

            candidate = stripped[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError as exc:
                raise LLMInvocationError(f"MiniMax 未返回可解析 JSON: {content}") from exc


def build_minimax_chat_model(settings: Settings | None = None) -> ChatOpenAI:
    active_settings = settings or get_settings()
    logger.info(
        "Configuring MiniMax client with timeout=%ss retries=%s model=%s",
        active_settings.minimax_timeout_seconds,
        active_settings.minimax_max_retries,
        active_settings.minimax_model,
    )
    return ChatOpenAI(
        model=active_settings.minimax_model,
        api_key=active_settings.openai_api_key,
        base_url=active_settings.openai_base_url,
        temperature=0.2,
        timeout=active_settings.minimax_timeout_seconds,
        max_retries=active_settings.minimax_max_retries,
    )


@lru_cache(maxsize=1)
def get_legal_triage_llm() -> LegalTriageLLM:
    return LegalTriageLLM(build_minimax_chat_model())
