---
name: autorepair-dev
description: Maintain and extend 汽車保養資料庫 (autorepair_db), the offline PyQt5 + SQLite Windows app for an elderly-run auto repair shop. Use for ANY task on this repo - bug fixes, new features, UI changes, data/schema changes, performance work, building the Windows exe, releases - and always finish with the retrospective that keeps this skill up to date.
---

# 汽車保養資料庫 — maintainer skill (single entry point)

This file is the **only entry point**. It tells you what to read for the task in
front of you; the details live in nested files next to it. Read only what the
task needs, but always do steps 1 and 4.

## 0. The app in 30 seconds

- Offline Windows desktop app, one portable exe (`汽車保養資料庫.exe`, PyInstaller
  onefile). No server, no network, no installer.
- Users: elderly shop owners who are not comfortable with computers. Every UI
  decision serves them: big text, big targets, Traditional Chinese only, one
  obvious main action per screen, confirmations before anything destructive.
- Records: 日期 / 車牌 / 金額 / 保養項目 (+ optional 公里數, 備註). Items are
  user-editable and permanent (soft delete).
- Pages: 新增紀錄 · 查詢紀錄 · 報表統計 · 備份/還原 · 設定.
- Data: SQLite in `autorepair_data/` next to the exe; daily auto backup; manual
  backup/restore to a single `.db` file (USB / cloud folder).
- Stack: Python 3.12, PyQt5 5.15, SQLite (stdlib), PyInstaller 6, Pillow (icon build only).

## 1. Before you start (always)

1. Read `knowledge/lessons.md` (the experience log) — past mistakes you must not repeat.
2. Read `knowledge/decisions.md` — product decisions the owner already made. Do
   not re-litigate them.
3. Run the tests: `python -m pytest -q tests` (must pass before and after).

## 2. Route to the right guide

| Your task | Read |
| --- | --- |
| Understand the code, find where something lives | `reference/architecture.md` |
| Any UI change (layout, new widget, colors, text) | `reference/design-system.md` |
| Run from source, screenshots, fake data, tests | `workflows/develop.md` |
| Add or change a feature end to end | `workflows/feature.md` |
| Fix a bug | `workflows/bugfix.md` |
| Change the database (columns, tables, queries) | `workflows/data-changes.md` |
| Anything touching lists/tables/queries, or "it is slow" | `workflows/performance.md` |
| Build the exe, test on Windows, release, version bump, icon | `workflows/build-release.md` |
| Finishing ANY task | `workflows/retro.md` (mandatory) |

## 3. Non-negotiable rules

- **Never lose user data.** Schema changes are additive and migrate in
  `_create_schema`; restore always makes a safety copy first; never delete
  records/items physically except a record the user explicitly deletes.
- **Elder-first UI.** Follow `reference/design-system.md`. All user-facing text
  is Traditional Chinese, short, and says what to do next.
- **Must not lag on old PCs with years of data.** Follow
  `workflows/performance.md`; run `tools/bench.py` after touching queries,
  tables, or page refresh logic.
- **Verify, don't assume.** Render screenshots (`tools/screenshot.py`) for any
  UI change and look at them; build and run the real exe on Windows before
  calling a release done.
- **No secrets in the repo** (it is public). Windows test host credentials come
  from the environment or the owner — see `workflows/build-release.md`.
- Commit messages end with the attribution line the harness gives you; push
  only when the owner asks.

## 4. Finish with the retrospective (always)

Do `workflows/retro.md`: update any reference/workflow file your change made
stale, append new lessons to `knowledge/lessons.md`, record new owner decisions
in `knowledge/decisions.md`. A task is not done until the skill matches the code.
