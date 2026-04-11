from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.knowledge.vector_store import (
    DEFAULT_INDEX_DIR,
    DEFAULT_KNOWLEDGE_DIR,
    DEFAULT_MODEL_NAME,
    ModelCachePathError,
    VectorStoreError,
    build_vector_store,
    rebuild_vector_store,
    update_vector_store,
    verify_vector_store,
)


def _print_result(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Knowledge vector store CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--knowledge-dir", default=str(DEFAULT_KNOWLEDGE_DIR))
    common.add_argument("--index-dir", default=str(DEFAULT_INDEX_DIR))
    common.add_argument("--model-name", default=DEFAULT_MODEL_NAME)

    sub.add_parser("build", parents=[common], help="Build vector store from knowledge jsonl files")
    sub.add_parser("update", parents=[common], help="Update vector store if knowledge changed")
    sub.add_parser("rebuild", parents=[common], help="Force rebuild vector store")

    verify_parser = sub.add_parser("verify", help="Verify vector store and D-drive model cache constraints")
    verify_parser.add_argument("--index-dir", default=str(DEFAULT_INDEX_DIR))

    args = parser.parse_args()

    try:
        if args.command == "build":
            result = build_vector_store(
                knowledge_dir=Path(args.knowledge_dir),
                index_dir=Path(args.index_dir),
                model_name=str(args.model_name),
            )
            _print_result(result)
            return 0
        if args.command == "update":
            result = update_vector_store(
                knowledge_dir=Path(args.knowledge_dir),
                index_dir=Path(args.index_dir),
                model_name=str(args.model_name),
            )
            _print_result(result)
            return 0
        if args.command == "rebuild":
            result = rebuild_vector_store(
                knowledge_dir=Path(args.knowledge_dir),
                index_dir=Path(args.index_dir),
                model_name=str(args.model_name),
            )
            _print_result(result)
            return 0
        if args.command == "verify":
            result = verify_vector_store(index_dir=Path(args.index_dir))
            _print_result(result)
            return 0
    except (VectorStoreError, ModelCachePathError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2

    print(json.dumps({"ok": False, "error": "unknown command"}, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
