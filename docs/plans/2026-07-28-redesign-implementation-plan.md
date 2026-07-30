# Implementation Plan: Telegram Mini App UI Redesign & Typography Excellence

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Telegram Mini App into a state-of-the-art interface with Google Fonts (`Plus Jakarta Sans` + `Inter`), Dark Space Glassmorphism, Cyrillic/Latin typographic hierarchy, responsive layouts, and Haptic Feedback.

**Architecture:** React 18 SPA using TailwindCSS + Custom Glassmorphism CSS variables + Telegram WebApp SDK theme matching.

**Tech Stack:** React 18, Vite, TailwindCSS, Google Fonts (Plus Jakarta Sans, Inter), lucide-react.

## Global Constraints

- **Typography**: `Plus Jakarta Sans` for Headings, `Inter` for Body & Controls.
- **Telegram Theme**: Seamless integration with dark/light client themes.

---

### Task 1: Google Fonts & CSS Design Tokens Setup

**Files:**
- Modify: `vacancy-spotter-app/frontend/index.html`
- Modify: `vacancy-spotter-app/frontend/src/index.css`

**Interfaces:**
- Consumes: Google Fonts API
- Produces: CSS typography classes (`font-heading`, `font-body`), glassmorphism utilities, and ambient glow nodes.

- [ ] **Step 1: Update index.html with Plus Jakarta Sans & Inter Google Fonts**

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap" rel="stylesheet">
```

- [ ] **Step 2: Update index.css with typography rules and glassmorphism styling**

```css
@layer base {
  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  }
  h1, h2, h3, h4, h5, h6, .font-heading {
    font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
  }
}

.glass-card {
  background: rgba(15, 23, 42, 0.75);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
```

- [ ] **Step 3: Commit changes**

```bash
git add vacancy-spotter-app/frontend/index.html vacancy-spotter-app/frontend/src/index.css
git commit -m "style(frontend): add Google Fonts and Glassmorphism design tokens"
```

---

### Task 2: React UI Redesign & Vercel Deployment

**Files:**
- Modify: `vacancy-spotter-app/frontend/src/App.tsx`

**Interfaces:**
- Consumes: Design system tokens & API endpoints
- Produces: High-end React Mini App UI with smooth onboarding, tariffs, haptic feedback, and Vercel deployment.

- [ ] **Step 1: Refactor App.tsx with modern visual hierarchy and Haptic feedback**

Apply typography classes (`font-heading`), Telegram HapticFeedback (`tg?.HapticFeedback?.impactOccurred('light')`), refined card layouts, and polished onboarding modal.

- [ ] **Step 2: Build & Deploy to Vercel**

Run command: `npm --prefix vacancy-spotter-app/frontend run build && npx vercel --prod --yes`
Expected output: Production deployment ready on Vercel.

- [ ] **Step 3: Commit changes**

```bash
git add vacancy-spotter-app/frontend/src/App.tsx
git commit -m "feat(frontend): complete UI redesign with Plus Jakarta Sans typography and glassmorphism"
```
