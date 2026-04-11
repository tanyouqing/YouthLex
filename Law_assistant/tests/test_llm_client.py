from app.services.llm_client import DeliverablesOutput, LegalTriageLLM, SimilarCaseOutput


def test_similar_case_output_accepts_string_value() -> None:
    case = SimilarCaseOutput.model_validate("示例案例/待后续接入案例库")

    assert case.title == "示例案例"
    assert "待后续接入案例库" in case.summary


def test_deliverables_output_normalizes_string_case_list() -> None:
    payload = DeliverablesOutput.model_validate(
        {
            "assistant_message": "总结",
            "demand_letter": "函件",
            "similar_cases": ["案例线索 1", "案例线索 2"],
        }
    )

    assert len(payload.similar_cases) == 2
    assert payload.similar_cases[0].title == "示例案例"
    assert payload.similar_cases[1].judgment == "待接入真实案例库。"


def test_extract_json_payload_uses_last_valid_json_code_block() -> None:
    raw_content = """
<think>debug text</think>

```json
{"assistant_message": "bad
```

```json
{"assistant_message": "good", "demand_letter": "letter", "similar_cases": []}
```
""".strip()

    payload = LegalTriageLLM._extract_json_payload(raw_content)

    assert payload["assistant_message"] == "good"
