# One-User Dataset Template

Use this template to create realistic benchmark sets aligned with the DocFoundry agent loop.

## 1. Topic

- Choose one coherent knowledge domain for a single user, one project, and one KB.
- Good examples: HR policy, incident response, vendor contracts, quarterly review.

## 2. Document Pack

Create 4-6 short documents with overlapping facts.

- a primary policy or handbook document
- an exception or clarification memo
- an operational workflow or runbook
- a FAQ, notes file, or status summary

Design rules:

- repeat important facts across 2-3 documents with slightly different wording
- include at least 2 dates or numeric thresholds
- include 1-2 exception paths
- include one workflow/procedure document
- include one doc that is helpful but not authoritative

## 3. Prompt Families

Create three prompt files per dataset:

- `planning_<topic>.txt`
- `synthesis_<topic>.txt`
- `refinement_<topic>.txt`

Each file should contain multiple prompt variants separated by `---`.

## 4. Planning Pattern

- Use the real planner contract from DocFoundry.
- Include `user_message`, `scope`, and `observations`.
- Make prompts ask for the next action only.

## 5. Synthesis Pattern

- Include `Question`, `Sources`, and `Context`.
- Use snippet citations like `[S1]`, `[S2]` and optional document labels like `[D1]`.
- Include 2-5 evidence snippets per case.

## 6. Refinement Pattern

- Start with a cited draft answer.
- Ask for stable formatting with no new claims.
- Preserve inline citations.

## 7. Coverage Checklist

- exact rule lookup
- threshold or deadline lookup
- exception handling
- workflow/approval path
- late or ambiguous case
- synthesis across 2-3 documents
- short summary question

## 8. Benchmark Levels

- `serve-only`: benchmark just generation via the gateway using prompt files
- `end-to-end`: benchmark real DocFoundry retrieval, database, vector search, and answer generation together
