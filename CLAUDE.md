# CLAUDE.md — Standing instructions for this repository

These are standing project instructions. Claude Code reads CLAUDE.md automatically at the start of every session. The specific task to perform is supplied per request; when a task is given, follow the Workflow below in order.

## Workflow

Follow these phases in order. Do not skip a phase unless the user tells you to.

0. **Pre-work questions.** Before any research, planning, or code reading, ask clarifying questions — one at a time. See the Question protocol below.
1. **External research.** If the task depends on external knowledge (library Application Programming Interfaces, framework features, official documentation, standards), read the primary sources online. Cite every external claim with a Uniform Resource Locator (URL).
2. **Plan drafting.** Write a phase-by-phase implementation plan in the project's existing plan format (the `docs/superpowers/plans/` directory when applicable).
3. **Quality Assurance agent review.** Dispatch a separate Quality-Assurance-focused subagent to review the plan for correctness, test coverage, edge cases, and verifiability. Pass the subagent the plan and a clear instruction to check the plan against the actual code in the repository.
4. **Architecture agent review.** Dispatch a separate Architecture-focused subagent to review the plan for layering, dependency direction, fit with existing patterns, and long-term maintenance cost.
5. **Code validation.** Confirm every file path, class name, method signature, configuration key, package name, namespace, and Application Programming Interface reference in the plan exists in the actual codebase. Read the files; do not rely on memory or prior conversation context.
6. **Final delivery.** Present the revised plan after incorporating the Quality Assurance review and the Architecture review and after code validation passes. State what changed between the draft and the final.

## Question protocol (Phase 0)

For each clarifying question, in this order:

1. **Background.** State why you are asking the question and what later work depends on the answer.
2. **Alternatives.** Provide at least two answer options in full prose paragraphs (N.A, N.B, optionally N.C). No one-line skeletons.
3. **Recommendation.** Recommend one option, following the "Plan & Recommendation Justification" rule in full: alternatives considered; criteria used, specific to this project; the tradeoff being accepted; the falsification condition (the circumstance under which the recommendation would reverse); ending with "My recommendation: <option>" plus numbered reasons.
4. **Explicit wording.** Write the entire question under the "Explicit, self-contained language" rules below.
5. **Wait for the answer** before asking the next question.

Ask only one question per message. After the user answers, ask the next one. Continue until you have everything you need before starting Phase 1.

## Explicit, self-contained language

Every word in your output must carry the same meaning to a reader who has not read the earlier parts of the conversation. Apply the following five constraints to every sentence you write, including clarifying questions, plan text, recommendations, and status updates.

1. **Name the object; never point at it.** Do not use "this", "that", "these", "those", "it", "them", "there", "the former", "the latter", "above", or "below" to stand in for something named earlier. Replace each pointer word with the full name of the object it refers to.
2. **Define every project-specific term the first time you use it.** A project-specific term is any word or phrase that names a system component, a person's role, a process, a file, a database table, or a piece of data particular to the project. On first use, write the full name, then a one-sentence definition in parentheses.
3. **No metaphors, idioms, or figurative language.** Use literal descriptions only. A non-native English speaker must be able to parse each sentence with a dictionary and no cultural knowledge.
4. **Expand every abbreviation and acronym on first use.** Write the full words, then the short form in parentheses. Example: "Structured Query Language (SQL)". Use the short form afterward.
5. **When a term repeats many times, define it once at the top.** Add a short "Terms used in this message" list at the start of the message, define each term once, then use the full name (never a pointer word) for every later mention.

If you cannot name an object precisely because you do not yet know its name, say so plainly rather than using a vague pointer word.

## Quality requirements

- **No hallucination.** Every method call, class name, file path, configuration key, package name, namespace, and external Application Programming Interface reference must be verified before it appears in any plan, answer, or recommendation. Verification means: read the file (for codebase claims) or fetch the Uniform Resource Locator (for external claims).
- **Cite codebase claims** with `[filename:lineNumber](relative/path#Lline)` so the user can open the source directly.
- **Cite external claims** with the Uniform Resource Locator of the source.
- **Flag uncertainty.** If you cannot verify a claim, state that you could not verify the claim. Do not fill the gap with a plausible guess.
- **No invented Application Programming Interfaces.** If a method, class, or option does not exist in the current version of the framework or library, do not write the method, class, or option into the plan. If you need a feature that does not exist, propose how to build the feature and mark the section explicitly as "new code to write".
- **Self-contained wording.** Follow the "Explicit, self-contained language" rules in every phase.

## Standing rules

The following named rules apply to every phase of every task without restatement:

- **Plain Language: No Metaphors or Idioms.** Use literal descriptions only (the same intent as constraint 3 of the "Explicit, self-contained language" section). Definition inferred from the rule name; the user may correct the wording.
- **Plan & Recommendation Justification.** Every recommendation states the alternatives considered, the project-specific criteria, the tradeoff accepted, the falsification condition, and ends with "My recommendation: <option>" plus numbered reasons (fully defined in Question protocol item 3).
- **Phase Completion: Verify Before Push.** Before claiming a phase or task is complete, and before any `git push`, run the relevant verification commands (tests, type-checking, linting) and confirm the output; state the evidence. Definition inferred from the rule name; the user may correct the wording.
- **Explicit, Self-Contained Language.** Defined in full in the "Explicit, self-contained language" section of CLAUDE.md.

If any of the standing rules and a per-request task prompt conflict, the per-request task prompt is narrower and takes precedence for that task only.
