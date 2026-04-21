# GEMINI.md

## Project Overview

**YF Monitor (智能房颤监测项目)** is a comprehensive system designed for monitoring atrial fibrillation (AF) using smart rings. It consists of a Django-based backend, an admin console, and a patient-facing web application that connects to hardware via the Web Bluetooth API.

### Architecture & Components
- **Backend (`/backend`):** Django 5 + Django REST Framework (DRF). Handles user authentication, device binding, data ingestion (packets), protocol parsing, risk analysis (rule-based and ML-based), and alert management.
- **Admin Console (`/console`):** Vue 3 + Vite + Element Plus + Pinia. A management interface for administrators to oversee accounts, devices, and system health.
- **Webapp (`/webapp`):** Vue 3 + Vite + Element Plus. A patient-facing portal that uses the **Web Bluetooth API** to directly connect to smart rings from Chromium-based browsers.
- **Documentation (`/document`):** VitePress-powered documentation site.

### Key Technologies
- **Backend:** Python 3.12+, Django 5, DRF, MySQL (Production) / SQLite (Dev), scikit-learn, LightGBM, Pandas, WFDB.
- **Frontend:** TypeScript (Strict), Vue 3 (Composition API), Vite, Element Plus, Pinia, ECharts.
- **Hardware Integration:** Web Bluetooth API (Service UUID: `bae80001-...`).

---

## Building and Running

### Backend (`cd backend`)
- **Environment:** Uses virtualenv at repo root (`.venv`).
- **Run Server:** `..\.venv\Scripts\python manage.py runserver`
- **Migrations:** `..\.venv\Scripts\python manage.py migrate`
- **Initial Setup:** `..\.venv\Scripts\python manage.py seed_demo_admin` (Admin: `admin` / `admin123456`)
- **Tests:** `..\.venv\Scripts\python manage.py test`
- **Mock Data:** `..\.venv\Scripts\python manage.py generate_mock_monitoring_data`

### Admin Console (`cd console`)
- **Install:** `npm install`
- **Dev Server:** `npm run dev` (Default: `http://127.0.0.1:3000`)
- **Build:** `npm run build` (Includes type-checking)

### Webapp (`cd webapp`)
- **Install:** `npm install`
- **Dev Server:** `npm run dev` (Default: `http://127.0.0.1:3001`)
- **Build:** `npm run build`

---

## Development Conventions

### Python / Django
- **Indentation:** 4 spaces.
- **Quotes:** Single quotes (`'`) for strings.
- **Logic Location:** Business logic belongs in `<app>/services.py`. Views should remain thin.
- **API Views:** Prefer Class-Based Views (CBVs). Explicitly set `permission_classes`.
- **Naming:** `snake_case` for functions/variables, `PascalCase` for classes.
- **Data Integrity:** `raw_payload` from devices must never be mutated. Analysis results are stored in sibling fields (`parsed`, `analysis`).

### TypeScript / Vue
- **Indentation:** 2 spaces.
- **Quotes:** Single quotes (`'`).
- **Semicolons:** **No** trailing semicolons.
- **SFC Structure:** `<script setup lang="ts">` with template first, script second. No scoped `<style>` blocks (use global `styles.css`).
- **Reactivity:** Use `ref()` for scalars and `reactive()` for objects.
- **State Management:** Composition API-style Pinia stores.
- **API Calls:** Always use the wrapper in `src/utils/api.ts` for consistent token handling.

### Hardware / BLE
- **Service UUID:** `bae80001-4f05-4503-8e65-3af1f7329d1f`
- **Write Char:** `...10`, **Notify Char:** `...11`.
- **Upload Endpoint:** `POST /api/v1/packets` with `source: 'web-bluetooth'`.

---

## Operational Notes
- **Security:** Do not commit `.env` files. Secrets are managed via environment variables.
- **Risk Mapping:** Use `format.ts` helpers in the frontend to ensure consistent risk level display.
- **ML Models:** Infrastructure for ML-based AF detection exists in `backend/monitoring/ml`, but rule-based logic (`rules-v1`) is the current default.
