from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List


TEMPLATES = {
    "hr_pto_one_user": [
        "employee_handbook_2025.md",
        "hr_policy_exceptions_memo.md",
        "manager_approval_workflow.md",
        "benefits_faq.md",
    ],
    "incidents_one_user": [
        "incident_postmortem_april.md",
        "oncall_runbook.md",
        "deployment_notes_april17.md",
        "known_issues.md",
    ],
    "contracts_one_user": [
        "master_services_agreement.md",
        "security_addendum.md",
        "order_form.md",
        "vendor_faq.md",
    ],
}


def tenant_slug(index: int) -> str:
    return f"tenant_{index:03d}"


def stamp_text(text: str, *, tenant_id: str, topic: str) -> str:
    banner = f"Tenant Scope: {tenant_id}\nTopic Pack: {topic}\n\n"
    return banner + text


def build_manifest(output_dir: Path, assignments: List[Dict[str, object]]) -> None:
    manifest = {
        "tenant_count": len(assignments),
        "tenants": assignments,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a multi-tenant corpus from one-user template packs.")
    parser.add_argument("--output-dir", default="data/generated/multi_tenant_corpus")
    parser.add_argument("--tenant-count", type=int, default=9)
    parser.add_argument(
        "--topics",
        nargs="+",
        default=["hr_pto_one_user", "incidents_one_user", "contracts_one_user"],
        choices=sorted(TEMPLATES.keys()),
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    corpus_root = root / "data" / "corpus"
    output_dir = (root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    assignments: List[Dict[str, object]] = []
    for idx in range(args.tenant_count):
        topic = args.topics[idx % len(args.topics)]
        tenant_id = tenant_slug(idx + 1)
        tenant_dir = output_dir / tenant_id
        docs_dir = tenant_dir / "documents"
        docs_dir.mkdir(parents=True, exist_ok=True)

        source_dir = corpus_root / topic
        created_docs = []
        for file_name in TEMPLATES[topic]:
            src = source_dir / file_name
            dst = docs_dir / file_name
            text = src.read_text(encoding="utf-8")
            dst.write_text(stamp_text(text, tenant_id=tenant_id, topic=topic), encoding="utf-8")
            created_docs.append({"file_name": file_name, "path": str(dst.relative_to(output_dir))})

        assignments.append(
            {
                "tenant_id": tenant_id,
                "topic": topic,
                "project_name": f"{tenant_id} {topic} project",
                "kb_name": f"{tenant_id} {topic} kb",
                "documents": created_docs,
            }
        )

    build_manifest(output_dir, assignments)
    print(f"Generated {len(assignments)} tenants -> {output_dir}")


if __name__ == "__main__":
    main()
