Generate a Lean 4 specification for the programming task in task/input.json.
Formalize the supplied natural-language description using the supplied signature,
imports and type auxiliaries. Use the two supplied few-shot examples consistently.

You may inspect the task workspace, edit candidate artifacts, run the supplied
local compiler/test tools and author your own programs or tests. Use only the
provided task information and permitted local tools. The harness's resource
limits apply to all work. Report unresolved ambiguity or inability to complete
the task in your retained work notes; do not invent benchmark reference answers.

Save the final candidate in candidate.json as exactly one JSON object with these
string fields: imports, precond_aux, precond, postcond_aux, postcond. Preserve the
supplied signatures. Keep your native candidate/check artifacts in the workspace.
There is no evaluator-guided correction after the attempt ends.
