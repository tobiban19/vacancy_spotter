# Bot Copywriting & Tone of Voice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update all user-facing copy in Telegram Mini App (`App.tsx`) and Telegram Bot (`bot_manager.py`) to align with "Пиши, сокращай" principles (Informational style: active voice, care for user, no corporate jargon or marketing fluff).

**Architecture:** Update string constants, toast notifications, labels, placeholders, and bot message callbacks directly in source code, then build frontend assets and test backend handlers.

**Tech Stack:** React, TypeScript, TailwindCSS, Python, aiogram 3 / Telethon.

## Global Constraints

- Follow "Пиши, сокращай": active voice, clear benefit first, no fluff, no fake enthusiasm.
- Maintain existing component interfaces and API payload formats.
- Ensure `npm run build` passes with zero errors.

---

### Task 1: Update Mini App Copy in `App.tsx`

**Files:**
- Modify: `c:/Users/ptimo/Documents/antigravity/vacancy-spotter-app/frontend/src/App.tsx`

- [ ] **Step 1: Update Onboarding Wizard & Instructions copy**
  Replace verbose and promotional copy in lines 435-645 of `App.tsx` with simple, active-voice statements.

- [ ] **Step 2: Update Profile & PDF upload copy**
  Replace jargon in lines 760-875 of `App.tsx` ("сильные стороны" -> "опыт и навыки", "Профиль успешно сохранен" -> "Сохранили изменения").

- [ ] **Step 3: Update Portfolio & Empty state copy**
  Replace evaluative copy in lines 880-990 of `App.tsx` ("лучших работ" -> "проекты").

- [ ] **Step 4: Update Subscription & Payment copy**
  Replace marketing fluff in lines 1070-1260 of `App.tsx` ("Тест-драйв" -> "7 дней подписки", "Я перевёл" -> "Отправить чек").

---

### Task 2: Update Telegram Bot Message Copy in `bot_manager.py`

**Files:**
- Modify: `c:/Users/ptimo/Documents/antigravity/vacancy-spotter/bot_manager.py`

- [ ] **Step 1: Update Inline Keyboard button labels and callback alerts**
  Replace button texts (lines 110-125) and callback messages (lines 135-230) with concise action verbs.

- [ ] **Step 2: Update Command responses and Statistics output**
  Replace passive voice and jargon in command handlers and `/stats` output (lines 240-295).

---

### Task 3: Build, Verify and Test System

**Files:**
- Verify: `vacancy-spotter-app/frontend` (Build)
- Verify: `vacancy-spotter` (Python tests / backend verification)

- [ ] **Step 1: Build Frontend Mini App**
  Run `npm run build` in `vacancy-spotter-app/frontend` and check for clean compilation.

- [ ] **Step 2: Verify Python Backend**
  Run pytest or python check on `bot_manager.py` to ensure no syntax or import errors.

- [ ] **Step 3: Verification Audit**
  Gather runtime verification that both frontend and bot are fully functional.
