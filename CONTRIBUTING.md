# Contributing to LuomiNest

[English](CONTRIBUTING.md) | [简体中文](CONTRIBUTING_zh.md) | [日本語](CONTRIBUTING_ja.md)

Thank you for your interest in contributing to **LuomiNest - Distributed Multi-User Relational AI Agent Platform**! We welcome contributions of all forms, including bug reports, feature suggestions, documentation enhancements, and code contributions.

Please review this guide to help you set up your development environment and adhere to our development workflow.

---

## Code of Conduct

All contributors and participants in the LuomiNest community are expected to uphold our [Code of Conduct](CODE_OF_CONDUCT.md) ([中文版](CODE_OF_CONDUCT_zh.md) / [日本語](CODE_OF_CONDUCT_ja.md)). Please report any unacceptable behavior to [luminouschenxi@outlook.com](mailto:luminouschenxi@outlook.com).

---

## How to Contribute

### 1. Reporting Bugs and Suggesting Features
- **Bug Reports**: Before reporting a bug, search existing [Issues](https://github.com/LuminousCX/LuomiNest/issues) to ensure it hasn't already been reported. Use our [Bug Report Template](https://github.com/LuminousCX/LuomiNest/issues/new?template=bug_report.yaml) and provide complete reproduction steps, logs, and environment details.
- **Feature Requests**: Discuss major feature proposals in [Discussions](https://github.com/LuminousCX/LuomiNest/discussions) or submit a [Feature Request](https://github.com/LuminousCX/LuomiNest/issues/new?template=feature_request.yaml) describing the problem, intended use case, and proposed interface.

### 2. Contributing Code
1. Check existing [Issues](https://github.com/LuminousCX/LuomiNest/issues) or create a new issue to discuss your planned changes.
2. Fork the repository and create a descriptive branch:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/issue-description
   ```
3. Set up the local environment, make your changes, and write relevant automated tests.
4. Run code formatting, type checking, and test suites locally.
5. Push your branch and open a Pull Request against the `master` branch.

---

## Local Development Environment Setup

### System Prerequisites
- **Python**: 3.12 or newer
- **Node.js**: 22 or newer
- **pnpm**: 10.x or newer
- **Docker**: Optional (for PostgreSQL, Redis, MQTT infrastructure)

### Backend Setup

```bash
cd backend

# Create and activate a Python virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# Install package in editable mode with development dependencies
pip install -e ".[dev]"

# Configure local environment variables
cp config/.env.example config/.env
# Edit config/.env to add your LLM API keys and model parameters

# Launch the backend development server
python main.py
```

The backend server runs on `http://127.0.0.1:18000` by default. Swagger API docs are accessible at `http://127.0.0.1:18000/docs`.

### Frontend Setup

```bash
cd frontend

# Install dependencies via pnpm
pnpm install

# Start the Vite development server with Electron desktop app
pnpm dev

# Build production artifacts
pnpm build
```

### Docker Infrastructure Services (Optional)

```bash
cd docker

# Start development infrastructure (PostgreSQL, Redis, MQTT)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

> **Note**: LuomiNest runs locally with a single SQLite database (WAL mode) by default. The PostgreSQL and Redis containers in Docker are reserved for cloud and distributed test environments.

---

## Quality Standards & Pre-Commit Verification

Before submitting a Pull Request, please ensure all relevant tests and linting checks pass cleanly.

### Backend Verification

```bash
cd backend

# Run automated test suite
pytest tests/

# Check code formatting and linting
ruff check app tests
ruff format --check app tests

# Run strict type checking
mypy app
```

### Frontend Verification

```bash
cd frontend

# Run TypeScript type check across web and node contexts
pnpm typecheck

# Verify production build compilation
pnpm build
```

---

## Coding Standards

### Python Standards
- Adhere strictly to **PEP 8**.
- Use explicit type annotations for all function arguments and return types.
- Format with **Ruff** (line length limit: `120`).
- Use `async`/`await` for all asynchronous I/O and database operations.
- Avoid wildcard imports (`from module import *`). Prefer explicit imports.
- Naming conventions: `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for module constants.

### TypeScript / Vue Standards
- Follow the Vue 3 Composition API with `<script setup lang="ts">`.
- Strict typing with TypeScript — avoid `any` wherever possible.
- Manage global UI state using Pinia stores.
- Clean component separation and reusable composables.
- Component filenames in `PascalCase.vue`, helper modules in `camelCase.ts`.

### Git Commit Conventions
Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

Format: `<type>(<scope>): <subject>`

**Allowed types:**
- `feat`: New feature or capability
- `fix`: Bug fix
- `docs`: Documentation update
- `style`: Formatting, missing semicolons, etc. (no production code change)
- `refactor`: Refactoring code without changing external behavior
- `test`: Adding or updating test cases
- `chore`: Maintenance, build tasks, dependency updates

**Examples:**
```
feat(memory): add per-member group chat persona tracking
fix(browser): restrict navigation tools to read-only visits
docs(readme): update v0.8.2 release highlights and links
refactor(security): unify token parsing and audit redaction
```

### Branch Naming Conventions
- `feature/<name>` — New feature development
- `fix/<name>` — Bug fixes
- `docs/<name>` — Documentation changes
- `refactor/<name>` — Code refactoring without behavioral change

---

## Model Assets Policy (Avatar / Voice Models)

Model asset files distributed with LuomiNest — built-in avatar models (Live2D, PixelPet, PNG Tuber, and future VRM/Spine samples) and bundled voice models — follow a **maintainer-only distribution** policy.

### Official Built-in Assets Are Maintained by the Core Team Only
The following paths are **not open for community asset submissions**. Pull Requests aiming to add, replace, or swap model binary assets under these paths will be closed without review:

- `frontend/src/renderer/public/live2d/` — built-in Live2D models
- `frontend/src/renderer/public/pixel/` — built-in PixelPet models
- `frontend/src/renderer/public/png/` — built-in PNG Tuber models
- `backend/models/` — bundled voice models
- `backend/app/data/avatar-manifest.json` — built-in model manifest

> Code changes that touch these paths (e.g., bug fixes to the model loader or manifest schema adjustments) are welcomed; additions of external model binaries are not.

### Why This Policy Exists
1. **Copyright and Redistribution Licenses**: Many avatar models and voice checkpoints circulating online lack redistribution permissions. Re-hosting them would expose the project and downstream users to copyright claims.
2. **Reviewability**: Binary archives cannot be inspected for malicious payloads, hidden licenses, or tampering. To maintain trust, only core maintainers provide verified models.

### User-Imported Models Stay on Your Local Machine
Models imported through the in-app Avatar Workshop (**皮套工坊 → Import Model**) are copied directly into the local application data directory (Electron `userData`), which resides **outside the git repository**. They are never committed and must not be submitted via PR.

### Requesting Official Built-in Models
If you represent an author or have models with verified redistributable open licenses (compatible with AGPL-3.0), please open an Issue detailing:
1. Model source and verified public license link.
2. Explicit permission for redistribution within an AGPL-3.0 project.

---

## Pull Request Guidelines

1. **Keep PRs Focused**: One PR should ideally solve one problem or implement one coherent feature. Smaller PRs are reviewed and merged much faster.
2. **Complete the Checklist**: Fill out the provided [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md).
3. **Verify Locally**: Ensure unit tests, `ruff`, `mypy`, and `pnpm typecheck` all pass before requesting a review.
4. **Respond to Reviews**: Engage constructively with review comments. We are happy to help get your code merged!

---

## Documentation Policy

The internal architecture and developer documentation suite (`文档/` directory) is retained in the local workspace only and is excluded from git via `.gitignore`. Do not attempt to commit local documentation drafts to git unless explicitly coordinated.

---

## License Agreement

By contributing to LuomiNest, you agree that your contributions will be licensed under the project's [GNU Affero General Public License v3.0](LICENSE).