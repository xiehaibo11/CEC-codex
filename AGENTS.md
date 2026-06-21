# Repository Guidelines

## Purpose
This file defines contributor rules for CEC-codex.
It is a code-management guide, not product documentation.
Keep it practical and update it when repository structure changes.
Keep this file between 300 and 500 lines.
If this file grows beyond 500 lines, split it by type or module.
Use short split names, for example `backend.md`, `frontend.md`, `data.md`, `ai.md`.
Store split files under `docs/code-management/`.
Keep `AGENTS.md` as the short entry point if splitting is needed.

## Project Overview
CEC-codex is a crypto perpetual trading platform.
The backend is FastAPI, SQLAlchemy, PostgreSQL, and APScheduler.
The frontend is React, Vite, TypeScript, Tailwind, and i18next.
The product supports Hyperliquid and Binance Futures.
It includes AI Trader, Program Trader, signals, factors, bots, and analytics.
FastAPI serves the production frontend from `backend/static/`.
Docker is supported, but some deployments run under systemd.
Treat trading, credentials, auth, and migrations as high-risk areas.

## Repository Structure
Root package scripts live in `package.json`.
Frontend package scripts live in `frontend/package.json`.
Backend Python dependencies live in `backend/pyproject.toml`.
Backend source lives in `backend/`.
Frontend source lives in `frontend/app/`.
Frontend public assets live in `frontend/public/`.
Built frontend assets live in `frontend/dist/`.
Served frontend assets live in `backend/static/`.
CoinGlass offline docs live in `CoinGlass API 介绍/`.
Backups live in `backups/`.
Screenshots live in `screenshots/`.
Avoid committing generated or private local artifacts.

## Backend Module Map
Use `backend/api/` for FastAPI routers.
Use `backend/routes/` only for existing legacy program routes.
Use `backend/services/` for business logic.
Use `backend/repositories/` for database query helpers.
Use `backend/schemas/` for Pydantic request and response models.
Use `backend/database/` for connections, ORM models, and migrations.
Use `backend/program_trader/` for Program Trader sandbox code.
Use `backend/factors/` for factor definitions.
Use `backend/config/` for prompts, guides, and settings.
Use `backend/skills/` for Hyper AI skill workflows.
Use `backend/utils/` for small shared utilities.

## Frontend Module Map
Use `frontend/app/components/` for React UI components.
Group components by domain, such as `hyper-ai`, `signal`, `program`, or `factor`.
Use `frontend/app/components/ui/` for reusable UI primitives.
Use `frontend/app/lib/` for API clients, hooks, and utilities.
Use `frontend/app/contexts/` for React context providers.
Use `frontend/app/locales/` for i18n text.
Use `frontend/public/` for public runtime assets.
Use the `@` alias for imports from `frontend/app`.
Avoid adding new top-level frontend folders without a clear reason.

## Code Management Rules
Keep modules focused on one domain.
Do not mix API routing, persistence, and business logic in one file.
Put validation near the API boundary or schema layer.
Put exchange-specific behavior in exchange clients or adapters.
Put reusable trading logic in services, not UI components.
Put UI formatting logic near the component that owns the view.
Prefer existing patterns over new abstractions.
Add abstractions only when they remove real duplication.
Keep public interfaces stable unless the change is intentional.
Document breaking changes in the PR description.

## Split Management Rules
Do not let one management document exceed 500 lines.
When splitting, keep names short and typed by domain.
Recommended split names are `backend.md`, `frontend.md`, `data.md`, `ai.md`, and `ops.md`.
Use `backend.md` for API, services, repositories, and migrations.
Use `frontend.md` for React, styling, routing, and i18n.
Use `data.md` for PostgreSQL, snapshots, K-lines, and analytics storage.
Use `ai.md` for Hyper AI, Prompt AI, Program AI, Signal AI, and tools.
Use `ops.md` for Docker, systemd, Nginx, env vars, and deployment.
Keep `AGENTS.md` as the table of contents after splitting.
Do not create long names such as `backend-service-code-management-guide.md`.
Prefer short names that are easy to reference in chat and PRs.
Run `backend/.venv/bin/python scripts/code_split_audit.py` before large refactors.

## Build Commands
Run `pnpm install:all` to install frontend packages and sync backend dependencies.
Run `pnpm dev` to start frontend and backend dev commands together.
Run `pnpm dev:frontend` to start Vite from `frontend/`.
Run `pnpm dev:backend` to start FastAPI with uvicorn on port `5611`.
Run `pnpm build:frontend` to build assets into `frontend/dist/`.
Run `pnpm build` to execute configured frontend and backend build steps.
Use Docker commands from `README.md` only when Docker deployment is intended.
On this server, check deployment notes before starting Docker.
Do not run a frontend dev server on production-like hosts.
For production static serving, copy built assets into `backend/static/`.

## Backend Commands
Run backend commands from `backend/` unless noted otherwise.
Run `uv sync` to install Python dependencies.
Run `uv run pytest` to execute backend tests.
Run `uv run pytest path/to/test_file.py::test_name` for one test.
Run `uv run ruff check .` to lint Python code.
Run `uv run black .` to format Python code.
Run `uv run uvicorn main:app --reload --port 8802` for local backend serving.
Use PostgreSQL before running backend integration paths.
Do not print or expose secret environment values.

## Python Style
Use Python 3.12 syntax.
Use 4-space indentation.
Use type hints for new public functions.
Use `snake_case` for functions, variables, and modules.
Use `PascalCase` for classes.
Use `UPPER_SNAKE_CASE` for constants.
Keep route handlers thin.
Move business logic into `services/`.
Move repeated SQLAlchemy query patterns into `repositories/`.
Prefer explicit exceptions with useful API messages.
Avoid broad `except Exception` unless the path is best-effort startup work.
Log context for operational failures.
Do not log private keys, API keys, tokens, or decrypted secrets.

## FastAPI Rules
Name router files `*_routes.py`.
Register new routers in `backend/main.py`.
Use `/api/<domain>` prefixes for business APIs.
Keep WebSocket logic in `backend/api/ws.py` or a dedicated service.
Use Pydantic models for non-trivial request bodies.
Use dependency functions for database sessions and auth.
Protect account-scoped routes with current-user ownership checks.
Keep response shapes stable for frontend clients.
Return clear errors for configuration problems.
Avoid blocking network calls inside hot endpoints when a cache exists.

## Database Rules
Main database models live in `backend/database/models.py`.
Snapshot database models live in `backend/database/snapshot_models.py`.
Do not mix main database sessions with snapshot database sessions.
Main DB connection is `database.connection.SessionLocal`.
Snapshot DB connection is `database.snapshot_connection.SnapshotSessionLocal`.
All migrations must be idempotent.
Add new migrations to `MIGRATIONS` in `backend/database/migration_manager.py`.
Check whether columns, tables, and indexes already exist before creating them.
Do not make startup depend on a migration that can safely be skipped.
Use SQLAlchemy models where practical.
Use raw SQL only when it is clearer or needed for migrations.
Keep data-retention and cleanup behavior explicit.

## Trading Safety Rules
Treat order placement as high-risk code.
Keep exchange signing code isolated in trading clients.
Keep Hyperliquid behavior in `hyperliquid_*` services or adapters.
Keep Binance behavior in `binance_*` services or adapters.
Validate environment values before trading.
Never mix `testnet` and `mainnet` state.
Persist decision logs for AI-driven trades.
Persist program execution logs for Program Trader actions.
Clamp or validate AI-provided prices before exchange submission.
Do not bypass wallet ownership or account ownership checks.
Preserve builder fee, broker, and rate-limit safeguards.
Manual verification is required for live-trading changes.

## AI System Rules
Hyper AI orchestration lives in `backend/services/hyper_ai_service.py`.
Hyper AI tools live in `backend/services/hyper_ai_tools.py`.
Tool risk handling lives in `backend/services/hyper_ai_harness.py`.
External tool config lives in `backend/services/hyper_ai_tool_registry.py`.
Skills live in `backend/skills/<skill-name>/SKILL.md`.
Keep skill names short and action-oriented.
Do not add write tools without risk classification.
Use confirmation flow for high-risk tool actions.
Keep model-provider quirks in shared LLM helper functions.
Preserve conversation memory limits and compression behavior.
Do not expose hidden prompt text through logs or tool output.

## Program Trader Rules
Program Trader models live in `backend/program_trader/models.py`.
Sandbox execution lives in `backend/program_trader/executor.py`.
Code validation lives in `backend/program_trader/validator.py`.
Do not weaken forbidden imports or forbidden function checks casually.
Strategy code must return a `Decision`.
Validate `Decision` fields before execution.
Keep backtest logic separate from live execution logic.
Record market queries when needed for later analysis.
Document any sandbox permission expansion.

## Factor and Signal Rules
Factor definitions live in `backend/services/factor_registry.py`.
Factor computation lives in `backend/services/factor_computation_service.py`.
Factor effectiveness lives in `backend/services/factor_effectiveness_service.py`.
Signal definitions and pools are managed through signal routes and services.
Signal detection should remain edge-triggered.
Avoid repeated triggers while a pool remains active.
Market flow collection should remain exchange-aware.
Keep factor names stable once stored in historical data.
Document changes to factor formulas or signal semantics.

## Frontend Style
Use TypeScript for new frontend files.
Use React function components.
Use `PascalCase` for component names.
Use `camelCase` for variables and functions.
Use domain folders for feature components.
Use UI primitives from `components/ui/` when available.
Use lucide icons where the project already uses them.
Keep API calls in `lib/` or domain-specific API helper files.
Keep global state in existing context providers when appropriate.
Avoid large components that combine data loading, layout, and complex formatting.
Split large UI components by visible subfeature.

## Frontend UX Rules
Keep operational screens dense, readable, and task-focused.
Avoid marketing-style pages inside the app shell.
Do not hide critical trading state behind hover-only UI.
Show loading, empty, error, and disabled states.
Keep button labels short and action-oriented.
Use tooltips for unfamiliar icon-only actions.
Keep text inside buttons and cards from overflowing.
Maintain mobile alternatives where existing screens have mobile components.
Check both English and Chinese text length.

## Internationalization Rules
Locale files live in `frontend/app/locales/`.
Add English and Chinese strings together.
Do not hardcode user-facing text in reusable components when locale keys exist.
Keep locale keys grouped by feature.
Use clear translation keys, not long sentence keys.
Confirm long Chinese labels fit compact controls.

## Testing Rules
Backend tests use `pytest`.
Name backend test files `test_*.py`.
Put tests near the changed domain when possible.
Cover migrations with schema or idempotency checks when risk is high.
Cover trading calculations with deterministic unit tests.
Cover auth ownership checks for account-scoped routes.
Cover Program Trader validation and execution changes.
There is no dedicated frontend test script currently.
Use `pnpm build:frontend` as the minimum frontend validation when practical.
Document manual verification if automated tests are not feasible.

## Review Checklist
Check whether the change touches live trading.
Check whether the change touches authentication.
Check whether the change touches encrypted credentials.
Check whether the change touches migrations.
Check whether the change touches startup services.
Check whether the change changes frontend API response assumptions.
Check whether bilingual text needs updates.
Check whether Docker volume mounts need updates for new backend paths.
Check whether background services need shutdown handling.
Check whether logs leak sensitive values.

## Commit Guidelines
Use short imperative commit messages.
Examples include `Add CoinIcon for watchlist displays`.
Examples include `Fix ccxt security and privacy vulnerability`.
Examples include `Document Hyper AI tool result visibility risk`.
Avoid vague messages such as `updates` or `changes`.
Mention the main module when useful.
Keep unrelated changes out of the same commit.
Do not commit generated files unless they are required for runtime.
Do not commit local deployment notes unless intentionally shared.

## Pull Request Guidelines
Describe the user-visible change.
List affected backend and frontend modules.
Call out database migrations.
Call out configuration or environment changes.
Call out trading, credential, auth, or privacy risk.
Include screenshots for visible UI changes.
Include test commands and manual verification.
Link related issues or incident notes when available.
Explain rollback steps for risky operational changes.

## Security and Configuration
Never commit `.env` files.
Never commit API keys.
Never commit private keys.
Never commit OAuth client secret JSON files.
Never commit database dumps unless explicitly required and sanitized.
Never commit encryption keys.
Keep CoinGlass paid keys server-side.
Frontend code should call `/api/coinglass`, not CoinGlass directly.
Keep Fernet encryption key persistence stable across deployments.
Mask secrets in logs, screenshots, and PR descriptions.

## Operations Notes
Docker commands are valid for Docker deployments.
Some servers run this project through systemd.
Check local deployment notes before changing process management.
Systemd service files are outside the repository.
Nginx config is outside the repository.
Do not restart production services without a clear reason.
For frontend production updates, build and sync static assets first.
For backend dependency updates, reinstall the backend package before restart.
For schema changes, verify startup migration logs.

## Final Contributor Rule
Prefer small, reviewable changes.
Read the surrounding code before editing.
Respect existing patterns unless they are clearly unsafe.
Keep trading safety above convenience.
Leave unrelated dirty worktree changes untouched.
