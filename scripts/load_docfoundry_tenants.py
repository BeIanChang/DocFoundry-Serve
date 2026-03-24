from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import httpx


def post_json(client: httpx.Client, url: str, payload: Dict, headers: Dict[str, str] | None = None) -> Dict:
    resp = client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()


def create_document_and_upload(
    client: httpx.Client,
    base_url: str,
    kb_id: str,
    file_path: Path,
) -> Dict:
    created = post_json(client, f"{base_url}/documents/", {"kb_id": kb_id, "title": file_path.stem})
    with file_path.open("rb") as handle:
        resp = client.post(f"{base_url}/documents/{created['id']}/upload", files={"file": (file_path.name, handle, "text/markdown")})
    resp.raise_for_status()
    return {"document": created, "upload": resp.json()}


def register_user(client: httpx.Client, base_url: str, tenant_id: str) -> Dict:
    email = f"{tenant_id}@benchmark.local"
    payload = {"email": email, "password": "benchmark-pass", "name": tenant_id}
    resp = client.post(f"{base_url}/auth/register", json=payload)
    if resp.status_code == 400 and "user already exists" in resp.text:
        resp = client.post(f"{base_url}/auth/login", json={"email": email, "password": "benchmark-pass"})
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Load generated tenant corpora into DocFoundry.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--corpus-dir", default="data/generated/multi_tenant_corpus")
    parser.add_argument("--output", default="data/generated/multi_tenant_corpus/load_results.json")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    corpus_dir = (root / args.corpus_dir).resolve()
    manifest = json.loads((corpus_dir / "manifest.json").read_text(encoding="utf-8"))
    output_path = (root / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    results: List[Dict] = []
    with httpx.Client(timeout=120.0) as client:
        for tenant in manifest.get("tenants", []):
            tenant_id = str(tenant["tenant_id"])
            auth = register_user(client, args.base_url, tenant_id)
            token = auth["token"]
            headers = {"Authorization": f"Bearer {token}"}

            project = post_json(client, f"{args.base_url}/projects/", {"name": tenant["project_name"]}, headers=headers)
            kb = post_json(
                client,
                f"{args.base_url}/kb/",
                {"project_id": project["id"], "name": tenant["kb_name"], "description": tenant["topic"]},
                headers=headers,
            )

            loaded_docs = []
            for doc in tenant.get("documents", []):
                rel_path = Path(str(doc["path"]))
                file_path = corpus_dir / rel_path
                loaded_docs.append(create_document_and_upload(client, args.base_url, kb["id"], file_path))

            results.append(
                {
                    "tenant_id": tenant_id,
                    "topic": tenant["topic"],
                    "token": token,
                    "project": project,
                    "kb": kb,
                    "document_ids": [entry["document"]["id"] for entry in loaded_docs],
                    "documents_loaded": len(loaded_docs),
                }
            )

    output_path.write_text(json.dumps({"tenants": results}, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"Loaded {len(results)} tenants -> {output_path}")


if __name__ == "__main__":
    main()
