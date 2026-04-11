# 知识库 Schema 设计（MVP）

> 说明：以下为 Demo 级结构设计，用于让辩论 Agent 快速跑通，不构成正式法律意见。

## 设计目标

- 同时支持四类核心知识：`statute`、`case`、`issue_rule`、`rebuttal_template`。
- 使用统一“记录信封（envelope）”结构，便于后续做混合检索、打分、版本升级。
- 保持 JSONL 友好：每条记录独立可读，可直接流式加载到内存、向量库或搜索引擎。
- 预留扩展字段：`source`、`quality_level`、`jurisdiction`、`scenario_tags`。

## 文件约定

- 主 Schema：`knowledge/schema/knowledge_record.schema.json`
- 示例数据：
  - `knowledge/statutes/statutes.demo.jsonl`
  - `knowledge/cases/cases.demo.jsonl`
  - `knowledge/issue_rules/issue_rules.demo.jsonl`
  - `knowledge/rebuttal_templates/rebuttal_templates.demo.jsonl`

## 统一记录结构

每条记录采用如下通用结构：

```json
{
  "record_id": "STATUTE_CN_0001",
  "record_type": "statute",
  "schema_version": "1.0.0",
  "jurisdiction": "CN-ML",
  "scenario_tags": ["rental_dispute"],
  "keywords": ["押金", "违约责任"],
  "quality_level": "demo",
  "source": {
    "source_type": "law_or_rule_or_mock",
    "citation": "《中华人民共和国民法典》第577条（示意）",
    "reliability": "medium"
  },
  "updated_at": "2026-04-07",
  "content": {}
}
```

## 为什么这样设计

- `record_type + content`：适合 LangGraph 检索节点按类型路由，也便于后续统一召回再重排。
- `scenario_tags`：与业务场景绑定（租房、兼职欠薪），未来可作为第一层过滤器。
- `source`：便于标注信息来源和可信度，后续可升级为官方法条库/裁判文书链接。
- `quality_level`：区分 demo 数据与正式生产数据，减少误用风险。
