# Realistic Agent-Loop Sample

## Planning

```text
You are an agent planner. Decide the NEXT action only.
Return ONLY valid JSON with keys: action, args, rationale.
Allowed actions: ["answer_with_context", "final", "get_document_profile", "grep_search", "keyword_search", "list_documents", "route_documents", "vector_search", "web_search"]
Rules:
- Keep rationale short (<= 1 sentence).
- Output must be JSON only. No markdown.
- If scope.document_id is set, do NOT route other documents.
- Avoid repeating the same action more than once in a run.
- If a list_documents/get_document_profile observation includes context_ready=true, you already have document summaries; proceed to answer_with_context or vector_search.
- If the user asks to list/show documents, choose list_documents.
- If you need evidence from docs, choose route_documents (optional) then vector_search then answer_with_context.
- Do NOT ask the user clarifying questions; make best-effort assumptions and proceed.
- If info is missing/ambiguous, prefer vector_search and then produce a final answer that states assumptions/uncertainty.
- Prefer keyword_search for exact terms (IDs, numbers, quoted phrases); vector_search for semantic queries.
- Prefer grep_search for regex/pattern matching or exact multi-line snippets.
- Use web_search for general internet queries not likely contained in the KB.
Args schema hints:
- final: {"answer": "..."}
- vector_search: {"query": "...", "top_k": <int optional>, "document_id": <str optional>}
- keyword_search: {"query": "...", "top_k": <int optional>, "document_id": <str optional>}
- grep_search: {"query": "re:... or /.../ or literal", "top_k": <int optional>, "document_id": <str optional>}
- web_search: {"query": "...", "top_k": <int optional>}

{"user_message":"What does the PTO policy say about carrying over unused vacation days into the next calendar year, and are there manager-approved exceptions?","scope":{"project_id":"proj_hr_demo","project_ids":["proj_hr_demo"],"folder_id":null,"kb_id":"kb_employee_handbook","document_id":null},"top_k":5,"max_doc_picks":5,"observations":[{"tool":"list_documents","context_ready":true,"documents":[{"document_id":"doc_handbook_2025","title":"Employee Handbook 2025"},{"document_id":"doc_hr_exceptions","title":"HR Policy Exceptions Memo"}]}]}
```

Expected shape:

```json
{"action":"vector_search","args":{"query":"PTO carry over unused vacation days manager-approved exceptions","top_k":5},"rationale":"Need direct handbook evidence and exception policy text."}
```

## Synthesis

```text
Question: What does the PTO policy say about carrying over unused vacation days into the next calendar year, and are there manager-approved exceptions?

Sources:
[D1] Employee Handbook 2025
[S1] Unused vacation days do not automatically carry over into the next calendar year. Employees are expected to schedule and use accrued vacation by December 31. Up to 5 unused days may be carried over only with written manager approval submitted before year end.
[S2] Carryover requests above 5 days require HR approval and are limited to exceptional business continuity situations.
[D2] HR Policy Exceptions Memo
[S3] Approved exceptions must document the reason, affected dates, approving manager, and HR acknowledgment when applicable.

Context:
[S1] Unused vacation days do not automatically carry over into the next calendar year. Employees are expected to schedule and use accrued vacation by December 31. Up to 5 unused days may be carried over only with written manager approval submitted before year end.

[S2] Carryover requests above 5 days require HR approval and are limited to exceptional business continuity situations.

[S3] Approved exceptions must document the reason, affected dates, approving manager, and HR acknowledgment when applicable.
```

Expected answer shape:

```text
Unused vacation days do not automatically carry over into the next calendar year; employees are expected to use them by December 31 [S1]. A manager may approve carryover of up to 5 unused days if the request is submitted in writing before year end [S1]. Requests above 5 days require HR approval and are reserved for exceptional business continuity cases [S2]. Approved exceptions should include the reason, affected dates, manager approval, and HR acknowledgment when applicable [S3].
```

## Refinement

```text
You are refining a draft answer for stability and formatting.
Preserve all factual claims and inline citations.
Return 3-4 concise bullets and do not introduce new claims.

Draft:
Unused vacation days do not automatically carry over into the next calendar year; employees are expected to use them by December 31 [S1]. A manager may approve carryover of up to 5 unused days if the request is submitted in writing before year end [S1]. Requests above 5 days require HR approval and are reserved for exceptional business continuity cases [S2]. Approved exceptions should include the reason, affected dates, manager approval, and HR acknowledgment when applicable [S3].
```

Expected answer shape:

```text
- Unused vacation days do not automatically carry over, and employees are expected to use them by December 31 [S1].
- A manager can approve carryover of up to 5 unused days if the request is submitted in writing before year end [S1].
- Requests above 5 days require HR approval and are limited to exceptional business continuity cases [S2].
- Approved exceptions should record the reason, affected dates, manager approval, and HR acknowledgment when applicable [S3].
```
