from __future__ import annotations

from app.graphs.legal_triage.state import EvidenceSlots, ScenarioValue
from app.services.retrieval_types import LegalBasisItem, SimilarCaseItem


SCENARIO_META: dict[ScenarioValue, dict[str, str]] = {
    "housing": {
        "label": "房屋与租赁纠纷",
        "subject": "关于租赁纠纷及押金返还的催告函",
        "counterparty_default": "房东/中介方",
        "authority": "属地住建/房屋租赁管理部门、12345 政务服务热线",
        "platform": "租房平台客服或交易平台投诉入口",
    },
    "labor": {
        "label": "劳动与兼职纠纷",
        "subject": "关于支付劳动报酬及纠正违法用工行为的催告函",
        "counterparty_default": "用人单位/负责人",
        "authority": "劳动保障监察部门、12333 人社热线",
        "platform": "招聘平台或兼职中介投诉入口",
    },
    "consumer": {
        "label": "消费与教培维权",
        "subject": "关于退费退款及停止侵权的催告函",
        "counterparty_default": "商家/平台/培训机构",
        "authority": "市场监督管理部门、12315 消费者投诉热线",
        "platform": "电商平台/教培平台售后与投诉入口",
    },
    "debt": {
        "label": "借贷与财产纠纷",
        "subject": "关于归还借款及停止拖延的催告函",
        "counterparty_default": "借款人/相关责任人",
        "authority": "属地法院立案渠道、学校保卫部门（如涉及校园风险）",
        "platform": "相关转账平台客服与交易记录导出入口",
    },
    "ip_reputation": {
        "label": "知识产权与名誉权纠纷",
        "subject": "关于停止侵权、删除内容并消除影响的催告函",
        "counterparty_default": "侵权发布者/平台运营方",
        "authority": "平台举报中心、学校网信或学生工作部门、公安机关（如涉嫌违法）",
        "platform": "发布平台举报、删除和申诉入口",
    },
    "other": {
        "label": "综合维权纠纷",
        "subject": "关于纠纷处理及履行义务的催告函",
        "counterparty_default": "相对方/责任方",
        "authority": "12345 政务服务热线或属地主管部门",
        "platform": "相关平台投诉或申诉入口",
    },
}


def build_legal_basis_notes(
    legal_basis_items: list[LegalBasisItem],
    scenario: ScenarioValue,
    retrieval_status: str,
) -> list[str]:
    if retrieval_status == "success" and legal_basis_items:
        notes: list[str] = []
        for item in legal_basis_items[:3]:
            title = f"《{item['title']}》"
            publisher = item["publisher"] or "相关主管机关"
            snippet = item["snippet"] or "可进一步结合全文核验具体适用规则。"
            notes.append(f"{title}（{publisher}）通常可作为本案参考依据：{snippet}")
        return notes

    if retrieval_status == "empty":
        return [f"暂未检索到与“{SCENARIO_META[scenario]['label']}”高度匹配的法规结果，当前仅能做初步判断。"]

    return [f"法律检索暂不可用，当前仅能结合“{SCENARIO_META[scenario]['label']}”的一般处理规则给出谨慎建议。"]


def build_action_plan(
    scenario: ScenarioValue,
    evidence_slots: EvidenceSlots,
    missing_slots: list[str],
    legal_basis_notes: list[str],
) -> list[str]:
    meta = SCENARIO_META[scenario]
    steps: list[str] = []

    if missing_slots:
        steps.append(
            "第一步：先补齐证据链。优先补充"
            + "、".join(_slot_label(slot) for slot in missing_slots[:3])
            + "，并统一整理为截图、录音、合同、转账记录等可提交材料。"
        )
    else:
        steps.append("第一步：立即固定现有证据。将聊天记录、合同约定、付款凭证、现场照片等材料按时间顺序整理备份。")

    counterparty = evidence_slots["counterparty"] or meta["counterparty_default"]
    steps.append(
        f"第二步：先礼后兵。今天就向{counterparty}发送催告函，并附上关键证据截图，要求其在明确期限内回复或履行义务。"
    )

    if scenario == "housing":
        steps.append(
            f"第三步：如对方拒绝处理，可同步向{meta['platform']}投诉，并向{meta['authority']}反映押金、维修责任或虚假房源问题。"
        )
        steps.append("第四步：若仍不解决，准备租赁合同、付款记录、交接记录后，通过调解、小额诉讼或法院起诉主张返还押金与赔偿。")
    elif scenario == "labor":
        steps.append(
            f"第三步：如对方拖延或拉黑，尽快向{meta['platform']}提交投诉，并向{meta['authority']}实名反映欠薪或违法收费问题。"
        )
        steps.append("第四步：准备考勤、工资约定、工作照片和聊天记录，必要时申请劳动仲裁，主张工资、赔偿或退还违规收费。")
    elif scenario == "consumer":
        steps.append(
            f"第三步：通过{meta['platform']}发起退款/售后投诉；如涉及虚假宣传、跑路或拒退费，再向{meta['authority']}投诉。"
        )
        steps.append("第四步：整理订单、宣传页面、聊天承诺、付款记录等材料，必要时向法院起诉要求退款、赔偿或解除合同。")
    elif scenario == "debt":
        steps.append(
            "第三步：明确书面还款期限，要求对方确认金额、还款时间与方式；若对方持续拖延，保留催款记录和拒不还款态度证据。"
        )
        steps.append(f"第四步：整理借款聊天、转账记录、借条等材料，通过{meta['authority']}或法院诉讼渠道追索借款；如涉及套路贷，优先报警并联系学校。")
    elif scenario == "ip_reputation":
        steps.append(
            f"第三步：通过{meta['platform']}提交删除、下架和侵权举报申请，并同步固定链接、截图、发布时间和传播范围证据。"
        )
        steps.append(f"第四步：如侵权持续，可向{meta['authority']}反映，并准备证据要求停止侵权、恢复名誉、赔礼道歉或赔偿损失。")
    else:
        steps.append(f"第三步：结合纠纷类型优先使用{meta['platform']}投诉，并同步联系{meta['authority']}寻求行政协助。")
        steps.append("第四步：如协商与投诉均无效，整理事实、证据和诉求，通过调解、仲裁或诉讼路径继续维权。")

    if legal_basis_notes:
        steps.append("第五步：对外沟通时可引用已检索到的法规依据，提高催告和投诉的说服力。")

    return steps


def build_demand_letter(
    scenario: ScenarioValue,
    evidence_slots: EvidenceSlots,
    legal_basis_notes: list[str],
    action_steps: list[str],
) -> str:
    meta = SCENARIO_META[scenario]
    counterparty = evidence_slots["counterparty"] or meta["counterparty_default"]
    time_place = evidence_slots["time_place"] or "待补充具体时间地点"
    amount = evidence_slots["amount"] or "待补充具体金额"
    agreement = evidence_slots["agreement"] or "双方已有明确约定，具体内容待补充"
    breach_fact = evidence_slots["breach_fact"] or "对方存在未履行约定或侵害合法权益的行为"
    evidence_text = "、".join(evidence_slots["existing_evidence"]) if evidence_slots["existing_evidence"] else "聊天记录、转账记录、合同/截图等证据材料"
    legal_basis_text = "\n".join(f"- {note}" for note in legal_basis_notes[:3]) or "- 目前可结合现有事实与一般法律规则主张权利，具体条文可后续补充核验。"
    action_text = "\n".join(f"- {step}" for step in action_steps[:3]) if action_steps else "- 请在合理期限内书面回复并履行义务。"

    return f"""# {meta['subject']}

**致：{counterparty}**

本人现就贵方与我之间的{meta['label']}相关争议，正式发出本函，请贵方收到后尽快处理。

## 一、基本事实

- 纠纷时间地点：{time_place}
- 涉及金额/标的：{amount}
- 主要约定：{agreement}
- 当前争议：{breach_fact}
- 现有证据：{evidence_text}

## 二、依据与说明

以下内容可作为当前维权与催告的主要参考：
{legal_basis_text}

贵方的相关行为已经对本人合法权益造成实质影响。为避免争议进一步扩大，请贵方立即停止拖延、拒绝履行或继续侵权的行为。

## 三、正式催告事项

请贵方在收到本函后尽快完成以下事项：
{action_text}

如贵方在合理期限内仍拒绝处理，本人将保留继续通过平台投诉、行政举报、仲裁或诉讼等方式维权的权利。

## 四、保留权利

本函仅为正式催告，不代表本人放弃任何进一步维权、索赔或追责的权利。
"""


def format_similar_cases_for_sidebar(
    similar_case_items: list[SimilarCaseItem],
    scenario: ScenarioValue,
) -> list[dict[str, str]]:
    formatted: list[dict[str, str]] = []
    for item in similar_case_items[:2]:
        court = item["court"] or "相关审理机关"
        date = item["judgement_date"] or "日期未披露"
        summary = item["summary"] or item["excerpt"] or "待补充案情摘要。"
        judgment = item["judgment"] or f"{item['judgement_type'] or '裁判结果'}，{date}"
        takeaway = item["takeaway"] or _default_case_takeaway(scenario)
        formatted.append(
            {
                "title": item["title"],
                "summary": f"【案情摘要】{summary}【审理机关】{court}【裁判日期】{date}",
                "judgment": f"【结果】{judgment}",
                "takeaway": f"【维权启示】{takeaway}",
            }
        )
    return formatted


def _slot_label(slot: str) -> str:
    mapping = {
        "counterparty": "相对方信息",
        "time_place": "时间地点",
        "amount": "标的金额",
        "agreement": "合同约定",
        "breach_fact": "违约事实",
        "existing_evidence": "现有证据",
    }
    return mapping.get(slot, slot)


def _default_case_takeaway(scenario: ScenarioValue) -> str:
    if scenario == "labor":
        return "优先保留考勤、聊天记录、付款约定和工作成果，便于后续投诉或仲裁。"
    if scenario == "housing":
        return "保留租赁合同、付款记录、交接视频和维修责任沟通记录，有助于主张押金与赔偿。"
    if scenario == "consumer":
        return "保留订单、宣传页面、退费承诺和客服沟通记录，便于向平台和监管部门投诉。"
    if scenario == "debt":
        return "固定借款聊天、转账记录和催款过程，有助于明确借贷关系与还款义务。"
    if scenario == "ip_reputation":
        return "及时固定网页链接、发布时间和传播范围证据，便于要求删除、澄清和追责。"
    return "尽量保留完整事实链和证据材料，便于后续投诉、调解或诉讼。"
