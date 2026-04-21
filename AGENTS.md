# AGENTS.md

Guide for agentic coding assistants working in this repo. Keep replies concise,
prefer editing existing files, match the conventions below. Detailed project
overview lives in `CLAUDE.md` / `CONFIG.md`; this file is the operational
cheat-sheet. No Cursor or Copilot rules exist in-tree.

## Layout

- `backend/` — Django 5 + DRF (Python 3). Apps: `accounts`, `devices`, `monitoring`.
- `console/` — Vue 3 + Vite + Element Plus + Pinia (TypeScript strict). Admin-facing.
- `webapp/` — Vue 3 + Vite + Element Plus + Pinia (TypeScript strict). Patient-facing,
  uses **Web Bluetooth API** (`navigator.bluetooth`) to connect rings in browser.
- `document/` — VitePress docs site.
- `study/`, `Android/` — legacy material, git-ignored, do not modify.

Virtualenv lives at repo root: `.venv/`. Always invoke via `..\.venv\Scripts\python`
from `backend/` on Windows (this is a Windows/PowerShell workspace).

## Build / Run / Test

### Backend (`cd backend`)
- Run server: `..\.venv\Scripts\python manage.py runserver`
- Apply migrations: `..\.venv\Scripts\python manage.py migrate`
- Config sanity check: `..\.venv\Scripts\python manage.py check`
- Seed demo admin (`admin` / `admin123456`): `..\.venv\Scripts\python manage.py seed_demo_admin`
- Full test suite: `..\.venv\Scripts\python manage.py test`
- One app: `..\.venv\Scripts\python manage.py test monitoring`
- One class: `..\.venv\Scripts\python manage.py test monitoring.tests.PacketParserTests`
- One test: `..\.venv\Scripts\python manage.py test monitoring.tests.PacketParserTests.test_parse_heart_rate_packet`
- Verbose / keep DB: append `-v 2` and/or `--keepdb` for fast reruns.
- Mock data: `...python manage.py generate_mock_monitoring_data`
- No lint/format tool is configured (no ruff/black/flake8). Match surrounding style.

### Console (`cd console`)
- Install: `npm install`
- Dev server: `npm run dev` (Vite, default `http://127.0.0.1:3000`)
- Production build (includes type-check): `npm run build`
- Type-check only: `npx vue-tsc --noEmit`
- Preview build: `npm run preview`
- No ESLint/Prettier/test runner configured. `tsconfig.json` has `strict`,
  `noUnusedLocals`, `noUnusedParameters`, `verbatimModuleSyntax` — respect them.

### Webapp (`cd webapp`)
- Install: `npm install`
- Dev server: `npm run dev` (Vite, default `http://127.0.0.1:3001`)
- Production build (includes type-check): `npm run build`
- Same `strict` + `verbatimModuleSyntax` rules as `console/`.
- BLE logic lives in `src/utils/ble.ts` (RingBleClient singleton) and
  `src/stores/ble.ts` (upload throttling, frame log). Service UUID is
  `bae80001-4f05-4503-8e65-3af1f7329d1f`; write `...10`, notify `...11`.
- Uploads go through `POST /api/v1/packets` with `source: 'web-bluetooth'`.
- Web Bluetooth only works on Chromium-based browsers over HTTPS or localhost.
- Token key: `yf-webapp-token` (console uses `yf-console-token` — keep them distinct).

### Docs (`cd document`)
- `npm run docs:dev` / `npm run docs:build` / `npm run docs:preview`.

## Python / Django conventions

- **Quotes**: single quotes everywhere (`'parsed'`, not `"parsed"`). 4-space indent.
- **Imports**: three groups separated by blank lines — stdlib, third-party
  (`django`, `rest_framework`), local. Within an app use relative imports
  (`from .models import ...`, `from .services import ingest_packet`). Across
  apps use absolute (`from devices.models import Device`).
- **Typing**: prefer PEP 585 builtins — `list[int]`, `dict[str, Any]`. Add
  `from __future__ import annotations` in modules that need forward refs
  (see `monitoring/services.py`). Use `@dataclass` for plain data containers.
- **Views**: class-based DRF (`APIView`, `generics.ListCreateAPIView`).
  Set `permission_classes` explicitly on every view; default to
  `permissions.IsAuthenticated` unless the endpoint is public (`AllowAny`).
- **Serializers**: one serializer per endpoint shape. Use `Meta.fields` lists
  (never `__all__`). Raise `serializers.ValidationError('中文提示')` in
  `validate_<field>` / `validate`.
- **Business logic** lives in `<app>/services.py`, not views. Views stay thin:
  validate → delegate → serialize → `Response(..., status=...)`.
- **Models**: declare `class Meta: ordering = [...]` and `related_name` on FKs.
  Use `TextChoices` for enums (see `accounts.User.Role`). Use
  `settings.AUTH_USER_MODEL`, not a direct import, for FKs to the user model.
  `User = get_user_model()` at module top where the user class is needed.
- **URLs**: live in `<app>/urls.py` and are mounted in `config/urls.py`.
  Paths generally omit trailing slashes (`'packets'`, `'measurements'`).
- **Tests**: `rest_framework.test.APITestCase`, method names `test_<behavior>`.
  Use `self.client.post(url, data, format='json')` and assert against
  `rest_framework.status` constants. Token auth:
  `self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')`.
- **Protocol parser invariant**: `raw_payload` is never mutated. New data is
  attached as `parsed` / `analysis` / `alert_state` siblings. Risk analysis is
  rule-based (`algorithm_version = 'rules-v1'`); do not introduce ML silently.
- **Settings**: read env via the `env_bool` / `env_list` helpers in
  `config/settings.py`. Secrets come from `backend/.env` (loaded manually).

## TypeScript / Vue conventions

- **Quotes / semicolons**: single quotes, **no trailing semicolons**, 2-space
  indent, trailing commas on multiline literals. Match existing files exactly.
- **SFCs**: always `<script setup lang="ts">`. Template first, script second,
  no `<style>` block — global styles live in `src/styles.css`.
- **Imports**: order is vue/pinia/router → third-party (`element-plus`,
  `axios`, `echarts`) → local (`../components`, `../stores`, `../utils`),
  with a blank line between groups. Use `import type { ... }` for type-only
  imports (`verbatimModuleSyntax` is on — mixed imports will fail build).
- **Reactivity**: `reactive()` for object state, `ref()` for scalars,
  `computed()` for derived values. Prefer composition-API Pinia stores:
  `defineStore('name', () => { ... return {...} })` (see `stores/auth.ts`).
- **HTTP**: always go through `api` from `src/utils/api.ts`. It injects the
  `Authorization: Token <token>` header and redirects to `/login` on 401.
  Never call `axios` directly or hardcode the base URL; respect
  `VITE_API_BASE_URL`.
- **Auth token** is stored in `localStorage` under `yf-console-token`; the
  user profile under `yf-console-user`. Bump `SESSION_VERSION` in
  `stores/auth.ts` if the shape changes.
- **Formatting helpers**: use `formatDateTime`, `riskLabel`, `riskTagType`
  from `src/utils/format.ts` — do not reinvent risk-level mapping.
- **Routing**: register lazy-loaded routes in `src/router/index.ts`. The
  `beforeEach` guard enforces `auth.isAuthenticated` and admin-only routes
  (`/dashboard`, `/accounts`, `/ai-settings`); add new admin pages to both
  places.
- **UI copy**: user-facing strings are Simplified Chinese; section eyebrows
  are English (e.g., `Risk distribution` + `风险等级分布`). Use `ElMessage`
  (`.success` / `.warning` / `.error`) for toasts.
- **Element Plus icons** are globally registered in `main.ts`; reference by
  name (e.g., `icon="Bell"`), don't re-import.
- **Types**: explicit `Array<Record<string, any>>` / typed refs over `any`
  when practical. Strict mode will reject unused locals and parameters.

## Error handling

- **Backend**: let DRF translate `ValidationError` into 400; use
  `get_object_or_404` for missing resources; wrap multi-write flows in
  `@transaction.atomic` or `with transaction.atomic():`.
- **Console**: wrap `api.*` calls in `try { ... } catch { ElMessage.error('…') }`
  with a Chinese message. 401 is handled globally by the axios interceptor —
  do not duplicate that logic.

## Naming

- Python: `snake_case` functions/vars, `PascalCase` classes, `UPPER_SNAKE`
  constants. Private helpers prefixed with `_`.
- Parsed device fields follow WeChat miniapp BLE naming (camelCase:
  `heartRate`, `hrv`, `wearStatusText`) — keep this on the wire even though
  the surrounding Python is snake_case.
- TS: `camelCase` for vars/functions, `PascalCase` for types/components,
  `SCREAMING_SNAKE` for module-level constants (`TOKEN_KEY`).
- Vue components: `PascalCase.vue`; view files suffixed `View.vue`.

## Workflow tips

- Plan non-trivial work with the TodoWrite tool and keep it updated.
- Prefer `Read` / `Edit` / `Write` over shell `cat` / `sed`.
- Before finishing a change, run the relevant checks: `manage.py test` +
  `manage.py check` for backend edits; `npm run build` for console edits.
- Do not introduce pagination, websockets, or ML models without explicit
  scope — those are called out as current non-goals.
