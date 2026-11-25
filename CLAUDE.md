# CLAUDE.md — Operating rules for Claude Code

Source: §0 of IMPLEMENTATION.md (the single source of truth for this project).

1. **Build only what this file describes.** Do not add features, pages, files, dependencies, abstractions, Docker, CI, databases, authentication, logging frameworks or "nice-to-haves" that are not listed here.
2. **Work one phase at a time.** At the end of every phase: stop, summarise what you built in plain English, show the exact command to verify it, and wait for the team to say "continue". Never start the next phase on your own.
3. **Ask before deviating.** If a step is unclear, a package is missing, or an API has changed, ask the team instead of guessing or improvising a workaround.
4. **No new packages** beyond §3 without asking first.
5. **Secrets:** the Gemini API key lives only in `.env`. Never print it, log it, hard-code it, paste it into any other file, or commit it. Create `.gitignore` (with `.env` in it) **before the first commit**. Commit only `.env.example`, which contains placeholder values.
6. **The verified correct answer is never modified by code.** Not by the LLM, not by suggestions, not by "cleaning". It can only be *flagged* for the teacher.
7. **Explainability:** every Python file starts with a short plain-English docstring that says *what this file does and why it exists*. Every phase ends with an entry in `docs/IMPLEMENTATION_LOG.md` (format in §8).
8. **Keep code simple and readable for students:** small functions, clear names, comments only where the *why* is not obvious. Use Pydantic models for data; avoid class hierarchies.
9. **Git:** make one commit per phase with the message given in that phase. **Never `git push`** unless the team says so.
10. Do not refactor or "improve" code from an earlier phase unless the current phase requires it.
