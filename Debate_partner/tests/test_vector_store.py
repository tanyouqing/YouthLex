import json
import pickle
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from app.knowledge import vector_store


class _FakeIndexFlatIP:
    def __init__(self, dim: int) -> None:
        self.dim = dim
        self.vectors = np.empty((0, dim), dtype="float32")

    def add(self, vectors: np.ndarray) -> None:
        self.vectors = np.vstack([self.vectors, vectors])

    def search(self, query: np.ndarray, top_k: int):
        if self.vectors.size == 0:
            distances = np.zeros((1, top_k), dtype="float32")
            indices = np.full((1, top_k), -1, dtype="int64")
            return distances, indices
        scores = np.dot(self.vectors, query[0])
        order = np.argsort(scores)[::-1]
        top = order[:top_k]
        dist = np.array([[float(scores[i]) for i in top]], dtype="float32")
        idx = np.array([[int(i) for i in top]], dtype="int64")
        return dist, idx

    @property
    def ntotal(self) -> int:
        return int(self.vectors.shape[0])


class _FakeFaissModule:
    IndexFlatIP = _FakeIndexFlatIP

    @staticmethod
    def write_index(index: _FakeIndexFlatIP, path: str) -> None:
        with open(path, "wb") as f:
            pickle.dump({"dim": index.dim, "vectors": index.vectors}, f)

    @staticmethod
    def read_index(path: str) -> _FakeIndexFlatIP:
        with open(path, "rb") as f:
            payload = pickle.load(f)
        index = _FakeIndexFlatIP(payload["dim"])
        index.vectors = payload["vectors"]
        return index


def _fake_encode_texts(texts, model_name):  # noqa: ARG001
    rows = []
    for text in texts:
        rows.append(
            [
                1.0 if "押金" in text else 0.0,
                1.0 if "合同" in text else 0.0,
                1.0,
            ]
        )
    return np.asarray(rows, dtype="float32")


class VectorStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        vector_store._load_index_bundle.cache_clear()

    def tearDown(self) -> None:
        vector_store._load_index_bundle.cache_clear()

    def test_model_cache_must_be_on_d_drive(self) -> None:
        with self.assertRaises(vector_store.ModelCachePathError):
            vector_store.ensure_model_cache_on_d_drive(Path(r"C:\temp\model_cache"))

    @patch("app.knowledge.vector_store._load_faiss", return_value=_FakeFaissModule())
    @patch("app.knowledge.vector_store._encode_texts", side_effect=_fake_encode_texts)
    @patch(
        "app.knowledge.vector_store.ensure_model_cache_on_d_drive",
        return_value={
            "HF_HOME": r"D:\cache\hf",
            "SENTENCE_TRANSFORMERS_HOME": r"D:\cache\st",
            "TRANSFORMERS_CACHE": r"D:\cache\tf",
            "TORCH_HOME": r"D:\cache\torch",
            "XDG_CACHE_HOME": r"D:\cache\xdg",
        },
    )
    def test_build_query_update_verify_chain(self, *_mocks) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            knowledge_dir = root / "knowledge"
            cases_dir = knowledge_dir / "cases"
            cases_dir.mkdir(parents=True, exist_ok=True)
            data_file = cases_dir / "cases.demo.jsonl"
            rows = [
                {
                    "record_id": "CASE_A",
                    "record_type": "case",
                    "scenario_tags": ["rental_dispute"],
                    "keywords": ["押金", "返还"],
                    "source": {"citation": "案例A"},
                    "content": {"case_title": "押金返还案", "court_reasoning": "押金可返还"},
                },
                {
                    "record_id": "CASE_B",
                    "record_type": "case",
                    "scenario_tags": ["rental_dispute"],
                    "keywords": ["合同", "成立"],
                    "source": {"citation": "案例B"},
                    "content": {"case_title": "合同成立案", "court_reasoning": "合同成立"},
                },
            ]
            data_file.write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
                encoding="utf-8",
            )
            index_dir = root / ".vector_store"

            build_result = vector_store.build_vector_store(
                knowledge_dir=knowledge_dir,
                index_dir=index_dir,
                model_name="fake-model",
            )
            self.assertEqual(build_result.get("updated"), True)
            self.assertEqual(build_result.get("record_count"), 2)

            hits, debug = vector_store.search_vector_store(
                query="请反驳押金返还主张",
                scenario_hint="rental_dispute",
                top_k=2,
                index_dir=index_dir,
            )
            self.assertEqual(debug.get("mode"), "vector")
            self.assertTrue(bool(hits))
            self.assertEqual(hits[0].get("record_id"), "CASE_A")

            verify_result = vector_store.verify_vector_store(index_dir=index_dir)
            self.assertEqual(verify_result.get("ok"), True)
            self.assertEqual(verify_result.get("record_count"), 2)

            update_result = vector_store.update_vector_store(
                knowledge_dir=knowledge_dir,
                index_dir=index_dir,
                model_name="fake-model",
            )
            self.assertEqual(update_result.get("updated"), False)


if __name__ == "__main__":
    unittest.main()
