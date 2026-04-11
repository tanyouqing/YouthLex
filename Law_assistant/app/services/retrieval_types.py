from typing import TypedDict


class LawSearchItem(TypedDict):
    id: str
    title: str
    publisher: str | None
    publish_date: str | None
    active_date: str | None
    timeliness: str | None
    level: str | None
    issued_no: str | None
    highlights: list[str]


class LawSearchResult(TypedDict):
    query_id: str | None
    total_count: int
    total_page: int
    items: list[LawSearchItem]


class LawDetailItem(TypedDict):
    id: str
    title: str
    publisher: str | None
    publish_date: str | None
    active_date: str | None
    timeliness: str | None
    level: str | None
    issued_no: str | None
    content: str


class CaseSearchItem(TypedDict):
    id: str
    title: str
    court: str | None
    case_number: str | None
    judgement_date: str | None
    judgement_type: str | None
    case_type: str | None
    cause: str | None
    level_of_trial: str | None
    publish_type_name: str | None
    content: str


class CaseSearchResult(TypedDict):
    query_id: str | None
    total_count: int
    total_page: int
    items: list[CaseSearchItem]


class LegalBasisItem(TypedDict):
    id: str
    title: str
    publisher: str | None
    publish_date: str | None
    active_date: str | None
    timeliness: str | None
    level: str | None
    snippet: str
    content: str | None


class SimilarCaseItem(TypedDict):
    id: str
    title: str
    court: str | None
    case_number: str | None
    judgement_date: str | None
    judgement_type: str | None
    case_type: str | None
    summary: str
    excerpt: str
    full_content: str
    judgment: str
    takeaway: str
