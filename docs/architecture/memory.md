# Memory

Runtime writes durable context pointers and artefacts; retrieval is explicit and bounded by task scope.

Learning/memory view:
- `diagram.learning-memory.mmd`

Context-resume contract:
- `opportunistic_resume_checkpoint` stores where opportunistic maintenance left off and candidate next items linked to context memory references.
- checkpoint lifecycle is contract-validated only in this milestone (no scheduler mutation).
