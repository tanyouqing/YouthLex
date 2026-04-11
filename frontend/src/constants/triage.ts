export const STAGE_META: Record<string, { label: string; icon: string; order: number }> = {
  empathy:          { label: "情绪安抚", icon: "💙", order: 1 },
  legal_grounding:  { label: "法律定性", icon: "⚖️", order: 2 },
  slot_filling:     { label: "证据补全", icon: "📋", order: 3 },
  action_plan:      { label: "维权指导", icon: "🗺️", order: 4 },
  deliverables:     { label: "交付生成", icon: "📄", order: 5 },
};

export const SLOT_LABELS: Record<string, string> = {
  counterparty:     "相对方",
  time_place:       "时间地点",
  amount:           "标的金额",
  agreement:        "合同/约定",
  breach_fact:      "违约事实",
  existing_evidence: "现有证据",
};

export const SCENARIO_OPTIONS: Array<{
  value: string;
  label: string;
  icon: string;
  example: string;
}> = [
  { value: "housing",       label: "住房租赁纠纷", icon: "🏠", example: "房东不退押金" },
  { value: "labor",         label: "劳动与兼职纠纷", icon: "💼", example: "老板拖欠兼职工资" },
  { value: "consumer",      label: "消费者维权",   icon: "🛒", example: "教培机构拒绝退费" },
  { value: "debt",          label: "民间借贷纠纷", icon: "💰", example: "同学借钱不还" },
  { value: "ip_reputation", label: "名誉与知识产权", icon: "🛡️", example: "校园论坛造谣网暴" },
  { value: "other",         label: "其他维权问题", icon: "🧭", example: "我这个问题不太确定属于哪一类" },
];
