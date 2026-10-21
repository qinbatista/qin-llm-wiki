---
name: testing-skill
description: Select focused generator and vault-runtime tests for memory isolation, integrity and preservation.
---

# Testing map

Run Python 3 with `-B` (`python3` on macOS/Linux; `py -3` on Windows). Bind `QIN_LLM_WIKI_TEST_CACHE` to the active task Cache before execution. Temporary generated stores never use production memory. Preserve hidden subprocess options and native platform branches.

| Purpose and goal | Level | Relative script | Runner |
| --- | --- | --- | --- |
| Current-index provenance, paths, readable links and canonical history integrity | 2 | qin_llm_wiki/templates/vault/AI Memory/tests/test_memory_lint.py | unittest discover in its parent |
| Exact-project prose/history retrieval, exact event identity versus mentions, and privacy-safe writes | 2 | qin_llm_wiki/templates/vault/AI Memory/tests/test_ai_memory.py | unittest discover in its parent |
| Explicit shared-rule promotion, project isolation and stable lesson bytes across unrelated closeouts | 2 | qin_llm_wiki/templates/vault/AI Memory/tests/test_auto_classify.py | unittest discover in its parent |
| Portable generator updates preserve user-owned facts and navigation | 2 | tests/test_generator.py | unittest discover -s tests -p test_generator.py |
| Hidden execution preserves subprocess results on supported hosts | 2 | tests/test_hidden_execution.py | unittest discover -s tests -p test_hidden_execution.py |

Update existing cases by purpose before adding scripts. Source parsing is level 1, not behavior acceptance. Full package/release validation is level 4 only when authorized publication requires it. Current outcomes and logs stay out of this map.
