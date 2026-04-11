# 得理开放平台 API 接入与服务层使用指南

本文基于官方文档 `D:/服创赛D06赛道帮助指引.docx` 整理，并结合项目内已经实现的服务层接口，给出一份适合后续节点开发直接复用的接入说明。

## 1. 能力概览

官方文档里与法律检索相关的核心接口有 3 个：

1. 类案检索：`POST /api/qa/v3/search/queryListCase`
2. 法规检索：`POST /api/qa/v3/search/queryListLaw`
3. 法规详情：`GET /api/qa/v3/search/lawInfo`

其中前两个负责“找列表”，第三个负责“拿法规全文内容”。

## 2. 鉴权方式

所有接口都通过请求头传递鉴权信息：

```http
Content-Type: application/json
appid: <你的 appid>
secret: <你的 secret>
```

为了避免把凭据硬编码进仓库，本项目采用两种安全用法：

1. 优先从环境变量读取：

```powershell
$env:DELILEGAL_APP_ID="你的_appid"
$env:DELILEGAL_SECRET="你的_secret"
```

2. 如果你手头只有官方 `docx`，客户端和测试脚本也支持从文档中自动提取演示凭据，不需要把凭据写进代码。

## 3. 当前服务接口分层

### 3.1 低层客户端

文件：`app/services/delilegal_client.py`

职责：

- 统一读取 `DELILEGAL_BASE_URL`、`DELILEGAL_APP_ID`、`DELILEGAL_SECRET`
- 统一组装请求头
- 统一处理 HTTP 错误、接口业务错误、响应结构错误
- 把官方原始 JSON 规范化成项目内部稳定结构

公开方法：

- `search_laws(...)`
- `get_law_detail(law_id, merge=True)`
- `search_cases(...)`

### 3.2 高层知识库门面

文件：`app/services/knowledge_base.py`

职责：

- 面向节点提供直接可用的检索结果
- “法条亮剑与定性”节点不需要再手动调 `lawInfo`
- “核心交付物生成”节点不需要再关心案例接口的原始字段

公开方法：

- `retrieve_legal_basis(query, scenario=None)`
- `retrieve_similar_cases(query, scenario=None)`

## 4. 项目内最推荐的调用方式

### 4.1 法条亮剑与定性

推荐直接调高层方法：

```python
from app.services.knowledge_base import LegalKnowledgeBase

with LegalKnowledgeBase() as knowledge_base:
    legal_basis = knowledge_base.retrieve_legal_basis(
        "学生兼职工资被拖欠，可以主张哪些法律依据？",
        scenario="labor",
    )
```

返回结果是结构化列表，每项至少包含：

- `id`
- `title`
- `publisher`
- `publish_date`
- `active_date`
- `timeliness`
- `level`
- `snippet`
- `content`

其中：

- `snippet` 适合直接给模型做定性摘要
- `content` 是已补齐的法规详情正文，可作为引用和生成依据

### 4.2 核心交付物生成

推荐直接调高层方法：

```python
from app.services.knowledge_base import LegalKnowledgeBase

with LegalKnowledgeBase() as knowledge_base:
    similar_cases = knowledge_base.retrieve_similar_cases(
        "房东无故不退押金，学生租客如何维权？",
        scenario="housing",
    )
```

返回结果是结构化列表，每项至少包含：

- `id`
- `title`
- `court`
- `case_number`
- `judgement_date`
- `judgement_type`
- `case_type`
- `summary`
- `excerpt`
- `full_content`

并额外保留了当前侧边栏占位结构兼容字段：

- `judgment`
- `takeaway`

### 4.3 什么时候直接用低层客户端

只有在这几种情况下，才建议节点或中间服务直接调用 `DeliLegalClient`：

- 你需要精细控制分页、排序、筛选字段
- 你想手动决定是否拉取法规详情
- 你要调试官方接口原始检索行为

## 5. 测试脚本怎么跑

推荐命令：

```powershell
.\.venv\Scripts\python.exe scripts\test_delilegal_api.py --guide-docx "D:\服创赛D06赛道帮助指引.docx"
```

如果你已经把凭据放进环境变量，也可以直接运行：

```powershell
.\.venv\Scripts\python.exe scripts\test_delilegal_api.py
```

脚本会输出并落盘以下文件：

- `docs/delilegal_api_samples/case_search.request.json`
- `docs/delilegal_api_samples/case_search.response.json`
- `docs/delilegal_api_samples/law_search.request.json`
- `docs/delilegal_api_samples/law_search.response.json`
- `docs/delilegal_api_samples/law_detail.response.json`
- `docs/delilegal_api_samples/README.md`

## 6. 类案检索接口

### 6.1 请求地址

```text
POST https://openapi.delilegal.com/api/qa/v3/search/queryListCase
```

### 6.2 推荐请求体格式

```json
{
  "pageNo": 1,
  "pageSize": 3,
  "sortField": "correlation",
  "sortOrder": "desc",
  "condition": {
    "keywordArr": [
      "上下班途中车祸引起的工伤保险案例"
    ]
  }
}
```

### 6.3 关键字段说明

- `pageNo`：页码
- `pageSize`：返回条数，比赛演示建议先取 `3-5`
- `sortField`：`correlation` 按相关性，`time` 按裁判时间
- `sortOrder`：`asc` / `desc`
- `condition.keywordArr`：关键词数组，必须是字符串数组
- `condition.longText`：长文本语义检索，通常与 `keywordArr` 二选一
- `condition.caseYearStart` / `condition.caseYearEnd`：裁判年份区间
- `condition.courtLevelArr`：法院层级数组
- `condition.judgementTypeArr`：文书类型数组

### 6.4 常见坑

- `keywordArr` 必须是 `["字符串"]` 这种数组，不是单个字符串。
- 如果用户输入是一整段案情，优先考虑映射到 `longText`。
- 比赛展示场景下，建议把返回结果再交给大模型做“类案摘要 + 裁判要点 + 可借鉴之处”的二次整理。

### 6.5 实测官方响应结构

官方原始响应里的案例列表在 `body.data`，不是 `body.records`。项目内低层客户端已经把它规范化为 `items`。

## 7. 法规检索接口

### 7.1 请求地址

```text
POST https://openapi.delilegal.com/api/qa/v3/search/queryListLaw
```

### 7.2 推荐请求体格式

```json
{
  "pageNo": 1,
  "pageSize": 3,
  "sortField": "correlation",
  "sortOrder": "desc",
  "condition": {
    "keywords": [
      "深圳市房地产相关的法律规定有哪些？"
    ],
    "fieldName": "semantic"
  }
}
```

### 7.3 关键字段说明

- `condition.keywords`：字符串数组
- `condition.fieldName`
  - `title`：按法规标题关键词检索
  - `semantic`：按自然语言问题做语义检索

### 7.4 实测官方响应结构

官方原始响应里的法规列表也在 `body.data`。列表项里的主键字段叫 `id`，后续拿详情时要把它当作 `lawId` 传给详情接口。

## 8. 法规详情接口

### 8.1 请求地址

```text
GET https://openapi.delilegal.com/api/qa/v3/search/lawInfo?lawId=<法规ID>&merge=true
```

### 8.2 用法说明

- `lawId` 来自法规检索接口返回列表中的法规 `id`
- `merge=true` 表示合并法规正文内容，不拆分条文段落

### 8.3 典型返回字段

- `title`：法规标题
- `publisherName`：发布机关
- `publishDate`：发布日期
- `activeDate`：生效日期
- `timelinessName`：时效性
- `lawDetailContent`：法规正文全文

### 8.4 实测官方响应结构

详情接口返回正文对象里的主键字段名通常是 `lawsId`，不是列表接口里的 `id`。项目内低层客户端已经统一规范为 `id`。

## 9. 低层客户端的实际返回结构

虽然官方原始响应里大量字段在 `body.data`、`body.lawDetailContent` 里，但项目内低层客户端已经做了规范化。

### 9.1 `search_laws(...)`

返回结构：

```python
{
    "query_id": "...",
    "total_count": 27,
    "total_page": 9,
    "items": [
        {
            "id": "...",
            "title": "...",
            "publisher": "...",
            "publish_date": "...",
            "active_date": "...",
            "timeliness": "...",
            "level": "...",
            "issued_no": "...",
            "highlights": [],
        }
    ],
}
```

### 9.2 `get_law_detail(...)`

返回结构：

```python
{
    "id": "...",
    "title": "...",
    "publisher": "...",
    "publish_date": "...",
    "active_date": "...",
    "timeliness": "...",
    "level": "...",
    "issued_no": "...",
    "content": "...",
}
```

### 9.3 `search_cases(...)`

返回结构：

```python
{
    "query_id": "...",
    "total_count": 280,
    "total_page": 94,
    "items": [
        {
            "id": "...",
            "title": "...",
            "court": "...",
            "case_number": "...",
            "judgement_date": "...",
            "judgement_type": "...",
            "case_type": "...",
            "cause": "...",
            "level_of_trial": "...",
            "publish_type_name": "...",
            "content": "...",
        }
    ],
}
```

## 10. 异常处理建议

客户端会把常见失败分成几类：

- `DeliLegalConfigError`
  - 没有配置 `DELILEGAL_APP_ID` / `DELILEGAL_SECRET`
- `DeliLegalTransportError`
  - 超时、网络不通、DNS 失败等请求层错误
- `DeliLegalHTTPError`
  - 对方返回非 `2xx`
- `DeliLegalAPIError`
  - 对方返回 `success=false` 或业务错误码
- `DeliLegalResponseError`
  - 对方字段缺失或结构与预期不一致

推荐做法：

- 节点里捕获这些异常后，向大模型或前端返回“检索暂时失败，请稍后重试”的可读提示
- 只有在调用成功但检索为空时，返回空列表，不要把空结果当异常

## 11. 样例输出文件说明

脚本运行完成后，`docs/delilegal_api_samples/` 里会保留本次测试的请求和规范化响应样例。你后续接 LangGraph 或 FastAPI 时，可以直接把这些文件当作内部接口契约参考。

建议优先查看：

1. `case_search.request.json`
2. `case_search.response.json`
3. `law_search.response.json`
4. `law_detail.response.json`

## 12. 比赛阶段的实现建议

- 不要让大模型“凭印象”回答法律问题，先检索再生成
- 回答中优先引用法规标题、案例标题、法院、裁判日期等可核验信息
- 对法规接口，列表检索和正文详情最好拆成两步
- 对案例接口，建议返回前 3 条并做结构化总结，不要把原始 JSON 直接展示给用户
