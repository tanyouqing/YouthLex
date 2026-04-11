from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_KNOWLEDGE_DIR = ROOT_DIR / "knowledge"
DEFAULT_INDEX_DIR = DEFAULT_KNOWLEDGE_DIR / ".vector_store"
DEFAULT_MODEL_NAME = "BAAI/bge-small-zh-v1.5"
MODEL_CACHE_ROOT = ROOT_DIR / ".model_cache"

INDEX_FILE_NAME = "faiss.index"
META_FILE_NAME = "metadata.jsonl"
MANIFEST_FILE_NAME = "manifest.json"

MODEL_CACHE_ENV_PATHS = {
    "HF_HOME": "hf_home",
    "SENTENCE_TRANSFORMERS_HOME": "sentence_transformers",
    "TRANSFORMERS_CACHE": "transformers",
    "TORCH_HOME": "torch",
    "XDG_CACHE_HOME": "xdg",
}


class ModelCachePathError(RuntimeError):
    pass


class VectorStoreError(RuntimeError):
    pass


def _resolve_path(path: Path | str) -> Path:
    return Path(path).expanduser().resolve()


def _is_d_drive(path: Path) -> bool:
    return path.drive.upper() == "D:"


def ensure_model_cache_on_d_drive(cache_root: Path | str | None = None) -> Dict[str, str]:
    enforce_d_drive = os.name == "nt"
    root = _resolve_path(cache_root or MODEL_CACHE_ROOT)
    if enforce_d_drive and not _is_d_drive(root):
        raise ModelCachePathError(f"MODEL_CACHE_PATH_INVALID: cache root must be on D drive, got: {root}")

    root.mkdir(parents=True, exist_ok=True)
    resolved_map: Dict[str, str] = {}
    for env_name, sub_dir in MODEL_CACHE_ENV_PATHS.items():
        configured = os.environ.get(env_name)
        target = _resolve_path(configured) if configured else _resolve_path(root / sub_dir)
        if enforce_d_drive and not _is_d_drive(target):
            raise ModelCachePathError(
                f"MODEL_CACHE_PATH_INVALID: {env_name} must be on D drive, got: {target}"
            )
        target.mkdir(parents=True, exist_ok=True)
        os.environ[env_name] = str(target)
        resolved_map[env_name] = str(target)

    return resolved_map


def _load_faiss() -> Any:
    try:
        import faiss  # type: ignore

        return faiss
    except Exception as exc:
        raise VectorStoreError("faiss-cpu is required for vector retrieval.") from exc


@lru_cache(maxsize=2)
def _get_embedder(model_name: str, cache_folder: str) -> Any:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception as exc:
        raise VectorStoreError("sentence-transformers is required for vector retrieval.") from exc
    return SentenceTransformer(model_name, cache_folder=cache_folder, device="cpu")


def _import_numpy() -> Any:
    try:
        import numpy as np  # type: ignore
    except Exception as exc:
        raise VectorStoreError("numpy is required for vector retrieval.") from exc
    return np


def _encode_texts(texts: List[str], model_name: str) -> Any:
    if not texts:
        np = _import_numpy()
        return np.empty((0, 0), dtype="float32")

    cache_paths = ensure_model_cache_on_d_drive()
    embedder = _get_embedder(model_name=model_name, cache_folder=cache_paths["SENTENCE_TRANSFORMERS_HOME"])
    vectors = embedder.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    np = _import_numpy()
    vectors = np.asarray(vectors, dtype="float32")
    if vectors.ndim == 1:
        vectors = vectors.reshape(1, -1)
    return vectors


def _load_records_from_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def discover_knowledge_files(knowledge_dir: Path | str = DEFAULT_KNOWLEDGE_DIR) -> List[Path]:
    base = _resolve_path(knowledge_dir)
    if not base.exists():
        return []

    files: List[Path] = []
    for path in base.rglob("*.jsonl"):
        if ".vector_store" in path.parts:
            continue
        files.append(path)
    files.sort()
    return files


def _file_digest(path: Path) -> Dict[str, Any]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    stat = path.stat()
    return {
        "path": str(path),
        "sha256": digest,
        "size": stat.st_size,
        "mtime": stat.st_mtime,
    }


def _flatten_content(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for item in value.values():
            yield from _flatten_content(item)
        return
    if isinstance(value, list):
        for item in value:
            yield from _flatten_content(item)
        return
    if value is None:
        return
    text = str(value).strip()
    if text:
        yield text


def _build_record_text(record: Dict[str, Any]) -> str:
    parts: List[str] = []
    parts.append(str(record.get("record_type", "")))
    parts.append(" ".join(str(x) for x in record.get("scenario_tags", []) if str(x).strip()))
    parts.append(" ".join(str(x) for x in record.get("keywords", []) if str(x).strip()))
    parts.append(str(record.get("source", {}).get("citation", "")))
    parts.extend(_flatten_content(record.get("content", {})))
    text = "\n".join([p for p in parts if p]).strip()
    return text[:8000]


def _build_snippet(record: Dict[str, Any]) -> str:
    content = record.get("content", {})
    record_type = record.get("record_type")
    if record_type == "statute":
        return f"{content.get('law_name', '')}{content.get('article_no', '')}：{content.get('plain_explanation', '')}".strip()
    if record_type == "case":
        return f"{content.get('case_title', '')}：{content.get('court_reasoning', '')}".strip()
    if record_type == "issue_rule":
        return f"{content.get('issue_name', '')}：{content.get('issue_definition', '')}".strip()
    if record_type == "rebuttal_template":
        return f"{content.get('template_type', '')}：{content.get('template_text', '')}".strip()
    return " ".join(_flatten_content(content))[:240]


def _collect_records(files: List[Path]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for file_path in files:
        for row in _load_records_from_jsonl(file_path):
            row["_source_file"] = str(file_path)
            records.append(row)
    return records


def _ensure_index_dir(index_dir: Path | str) -> Path:
    path = _resolve_path(index_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _index_file_paths(index_dir: Path) -> Tuple[Path, Path, Path]:
    return (
        index_dir / INDEX_FILE_NAME,
        index_dir / META_FILE_NAME,
        index_dir / MANIFEST_FILE_NAME,
    )


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    path.write_text("\n".join(lines), encoding="utf-8")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _load_manifest(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_vector_store(
    knowledge_dir: Path | str = DEFAULT_KNOWLEDGE_DIR,
    index_dir: Path | str = DEFAULT_INDEX_DIR,
    model_name: str = DEFAULT_MODEL_NAME,
) -> Dict[str, Any]:
    cache_paths = ensure_model_cache_on_d_drive()
    files = discover_knowledge_files(knowledge_dir)
    if not files:
        raise VectorStoreError("No knowledge jsonl files found for indexing.")

    records = _collect_records(files)
    if not records:
        raise VectorStoreError("No knowledge records found for indexing.")

    texts = [_build_record_text(record) for record in records]
    embeddings = _encode_texts(texts, model_name=model_name)
    if embeddings.shape[0] == 0:
        raise VectorStoreError("Embedding generation failed: empty embedding matrix.")

    faiss = _load_faiss()
    dim = int(embeddings.shape[1])
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    metadata: List[Dict[str, Any]] = []
    for idx, record in enumerate(records):
        metadata.append(
            {
                "vector_id": idx,
                "record_id": str(record.get("record_id", "")),
                "record_type": str(record.get("record_type", "")),
                "scenario_tags": [str(x) for x in record.get("scenario_tags", [])],
                "keywords": [str(x) for x in record.get("keywords", [])],
                "citation": str(record.get("source", {}).get("citation", "")),
                "snippet": _build_snippet(record),
                "source_file": str(record.get("_source_file", "")),
            }
        )

    index_path, meta_path, manifest_path = _index_file_paths(_ensure_index_dir(index_dir))
    faiss.write_index(index, str(index_path))
    _write_jsonl(meta_path, metadata)

    manifest = {
        "schema_version": "1.0.0",
        "model_name": model_name,
        "vector_dim": dim,
        "record_count": len(metadata),
        "knowledge_dir": str(_resolve_path(knowledge_dir)),
        "built_at": datetime.now().isoformat(),
        "files": [_file_digest(path) for path in files],
        "cache_paths": cache_paths,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    _load_index_bundle.cache_clear()
    return {
        "updated": True,
        "record_count": len(metadata),
        "index_dir": str(_ensure_index_dir(index_dir)),
        "model_name": model_name,
    }


def update_vector_store(
    knowledge_dir: Path | str = DEFAULT_KNOWLEDGE_DIR,
    index_dir: Path | str = DEFAULT_INDEX_DIR,
    model_name: str = DEFAULT_MODEL_NAME,
) -> Dict[str, Any]:
    ensure_model_cache_on_d_drive()
    idx_dir = _ensure_index_dir(index_dir)
    _, _, manifest_path = _index_file_paths(idx_dir)
    old_manifest = _load_manifest(manifest_path)
    current_files = discover_knowledge_files(knowledge_dir)
    current_digests = [_file_digest(path) for path in current_files]

    if (
        old_manifest
        and old_manifest.get("model_name") == model_name
        and old_manifest.get("files") == current_digests
    ):
        return {
            "updated": False,
            "record_count": int(old_manifest.get("record_count", 0)),
            "index_dir": str(idx_dir),
            "model_name": model_name,
        }

    return build_vector_store(knowledge_dir=knowledge_dir, index_dir=idx_dir, model_name=model_name)


def rebuild_vector_store(
    knowledge_dir: Path | str = DEFAULT_KNOWLEDGE_DIR,
    index_dir: Path | str = DEFAULT_INDEX_DIR,
    model_name: str = DEFAULT_MODEL_NAME,
) -> Dict[str, Any]:
    return build_vector_store(knowledge_dir=knowledge_dir, index_dir=index_dir, model_name=model_name)


def verify_vector_store(index_dir: Path | str = DEFAULT_INDEX_DIR) -> Dict[str, Any]:
    cache_paths = ensure_model_cache_on_d_drive()
    faiss = _load_faiss()
    idx_dir = _ensure_index_dir(index_dir)
    index_path, meta_path, manifest_path = _index_file_paths(idx_dir)

    missing = [str(path) for path in (index_path, meta_path, manifest_path) if not path.exists()]
    if missing:
        raise VectorStoreError(f"Vector store files missing: {missing}")

    index = faiss.read_index(str(index_path))
    metadata = _read_jsonl(meta_path)
    manifest = _load_manifest(manifest_path)
    if int(index.ntotal) != len(metadata):
        raise VectorStoreError(
            f"Vector store inconsistency: index.ntotal={index.ntotal}, metadata={len(metadata)}."
        )

    if int(manifest.get("record_count", -1)) != len(metadata):
        raise VectorStoreError("Manifest record_count does not match metadata length.")

    return {
        "ok": True,
        "record_count": len(metadata),
        "index_dir": str(idx_dir),
        "model_name": str(manifest.get("model_name", "")),
        "cache_paths": cache_paths,
    }


@lru_cache(maxsize=2)
def _load_index_bundle(index_dir: str) -> Tuple[Any, List[Dict[str, Any]], Dict[str, Any]]:
    faiss = _load_faiss()
    idx_dir = _ensure_index_dir(index_dir)
    index_path, meta_path, manifest_path = _index_file_paths(idx_dir)
    if not index_path.exists() or not meta_path.exists() or not manifest_path.exists():
        raise VectorStoreError("Vector store is not built yet. Please run index_cli build first.")
    index = faiss.read_index(str(index_path))
    metadata = _read_jsonl(meta_path)
    manifest = _load_manifest(manifest_path)
    return index, metadata, manifest


def _rerank_with_scenario(
    rows: List[Tuple[Dict[str, Any], float]],
    scenario_hint: str,
    top_k: int,
) -> List[Tuple[Dict[str, Any], float]]:
    scenario = scenario_hint.strip().lower()
    boosted: List[Tuple[Dict[str, Any], float]] = []
    for meta, score in rows:
        scenario_tags = [str(x).lower() for x in meta.get("scenario_tags", [])]
        if scenario and scenario in scenario_tags:
            score += 0.08
        boosted.append((meta, score))

    boosted.sort(key=lambda item: item[1], reverse=True)
    if len(boosted) <= top_k:
        return boosted

    selected: List[Tuple[Dict[str, Any], float]] = []
    used_types: set[str] = set()
    for meta, score in boosted:
        record_type = str(meta.get("record_type", ""))
        if record_type and record_type in used_types:
            continue
        selected.append((meta, score))
        if record_type:
            used_types.add(record_type)
        if len(selected) >= top_k:
            return selected

    for meta, score in boosted:
        if len(selected) >= top_k:
            break
        if (meta, score) not in selected:
            selected.append((meta, score))

    return selected


def search_vector_store(
    query: str,
    scenario_hint: str = "",
    top_k: int = 6,
    index_dir: Path | str = DEFAULT_INDEX_DIR,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    query = str(query or "").strip()
    if not query:
        return [], {"mode": "vector", "error_code": "EMPTY_QUERY"}

    ensure_model_cache_on_d_drive()
    index, metadata, manifest = _load_index_bundle(str(_resolve_path(index_dir)))
    model_name = str(manifest.get("model_name", DEFAULT_MODEL_NAME))
    query_vec = _encode_texts([query], model_name=model_name)

    candidate_k = min(max(top_k * 4, top_k), max(len(metadata), top_k))
    distances, indices = index.search(query_vec, candidate_k)
    scored_rows: List[Tuple[Dict[str, Any], float]] = []
    for distance, idx in zip(distances[0], indices[0]):
        if int(idx) < 0 or int(idx) >= len(metadata):
            continue
        meta = metadata[int(idx)]
        scored_rows.append((meta, float(distance)))

    reranked = _rerank_with_scenario(scored_rows, scenario_hint=scenario_hint, top_k=top_k)
    hits: List[Dict[str, Any]] = []
    for meta, score in reranked:
        hits.append(
            {
                "record_id": str(meta.get("record_id", "")),
                "record_type": str(meta.get("record_type", "issue_rule")),
                "score": int(max(score, 0.0) * 100),
                "citation": str(meta.get("citation", "")),
                "snippet": str(meta.get("snippet", "")),
            }
        )

    debug = {
        "mode": "vector",
        "error_code": "",
        "index_record_count": len(metadata),
        "model_name": model_name,
    }
    return hits, debug
