# Retrospective (mandatory at the end of every task)

The skill is this project's memory. Another agent will maintain the app using
only this skill, so it must describe the code **as it is now** and carry
forward what was learned. Spend a few minutes on this every time.

## Steps

1. **Diff the knowledge against the change.** List what you changed (files,
   behaviour, commands). For each item ask: which skill file describes this?
   - module/flow/schema → `reference/architecture.md`
   - visuals, components, roles, sizing → `reference/design-system.md`
   - how to run/test/build/release → the matching `workflows/*.md`
   - budgets / new hot paths → `workflows/performance.md` (update "Last measured")
   - a new kind of task → add a workflow file **and** a row in the routing
     table in `SKILL.md` (SKILL.md stays the single entry point)
   Edit those files so they are true again. Delete statements that are no
   longer true — stale guidance is worse than none.
2. **Precipitate experience.** Append to `knowledge/lessons.md` every
   non-obvious thing you learned: a mistake you made and its cause, a tool
   quirk, a trap in Qt/PyInstaller/Windows, a user reaction. Use the entry
   format there. If a lesson is now a rule, also promote it into the relevant
   workflow/reference file and note "promoted" in the lesson.
3. **Record decisions.** Anything the owner decided (product, wording, scope,
   style) goes into `knowledge/decisions.md` with the date and reason.
4. **Prune.** If `lessons.md` has entries that repeat or are fully captured
   by rules elsewhere, merge them. Keep each file short enough to read in one go.
5. **Check the entry point.** Re-read `SKILL.md`: does the routing table still
   cover every workflow file? Are the non-negotiable rules still right?
6. Commit the skill changes together with the code change.

## Quality bar

- Concrete over generic: commands, file names, numbers, error messages.
- Explain *why* for every rule so future agents can judge edge cases.
- Never put secrets (passwords, hosts, personal data) in the skill — the repo
  is public.
