# HR PTO One-User Dataset

This dataset is a realistic starter pack for a single user querying one HR knowledge base.

## Topic

- PTO carryover policy, exception handling, and approval workflow.

## Document Pack

- `data/corpus/hr_pto_one_user/employee_handbook_2025.md`
- `data/corpus/hr_pto_one_user/hr_policy_exceptions_memo.md`
- `data/corpus/hr_pto_one_user/manager_approval_workflow.md`
- `data/corpus/hr_pto_one_user/benefits_faq.md`

## Task Set

- 8 planning prompts in `data/prompts/planning_hr_pto_one_user.txt`
- 8 synthesis prompts in `data/prompts/synthesis_hr_pto_one_user.txt`
- 8 refinement prompts in `data/prompts/refinement_hr_pto_one_user.txt`

## Intended Retrieval/Citation Pattern

- Planning simulates the actual JSON-only planner request.
- Synthesis uses `Question`, `Sources`, and `Context` with inline snippet citations such as `[S1]` and `[S2]`.
- Refinement preserves those snippet citations while forcing stable bullet output.

## Coverage

- default carryover rule
- 5-day manager-only threshold
- HR approval path for requests above 5 days
- late request handling
- exception documentation requirements
- March 31 usage deadline
- multi-document synthesis questions
