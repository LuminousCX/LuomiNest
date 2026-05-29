# Contributing to LuomiNest

Thank you for your interest in contributing to LuomiNest - Distributed AI Companion Platform! This guide will help you set up your development environment and understand our development workflow.

## Quick Start

1. Check existing [Issues](https://github.com/LuminousCX/LuomiNest/issues) and [Discussions](https://github.com/LuminousCX/LuomiNest/discussions)
2. Fork the repository and create a branch
3. Run the local development environment
4. Make focused changes
5. Run checks and open a Pull Request

---

## Trae Code Modification Rules (Final Version)

**Highest Priority Principle: Better to delete and rewrite than patch on incorrect code. Any modification that breaks correctness must be completely deleted, no matter how powerful the functionality.**

### I. Pre-Check Rules (Must be 100% Complete Before Modification)

1. **Must Read All Related Files Completely**
   - First look at existing code implementation logic, then start writing any code
   - Must confirm whether the feature you want to implement **already exists**, absolutely no duplicate implementation
   - Must understand the design intent of existing architecture, cannot break the overall structure
   - Forbidden: Giving "complete implementation" without reading the code first

2. **Must Verify Original Logic is Correct First**
   - First run existing code, confirm where the problem actually lies
   - Distinguish between "design flaw" and "code bug"
   - If it's a design flaw, directly refactor the entire module, don't patch
   - If it's a code bug, only fix the bug itself, don't change other unrelated logic

3. **Must Clearly Define Modification Scope**
   - Only modify files directly related to the current task
   - Absolutely cannot modify parts the user didn't request
   - Forbidden: Casual refactoring, style optimization, adjusting unrelated code

### II. Error Handling Rules (Must Execute When Errors Found)

1. **Found You Misunderstood the Requirement → Stop Immediately, Full Rollback**
   - Delete all code from this modification, including new files, functions, variables
   - Don't leave any commented-out code, unused functions
   - Re-confirm requirements, then write correct code from scratch
   - Forbidden: Continue modifying based on wrong understanding, trying to "compat"

2. **Found Previous Modification Was Wrong → Delete All Immediately**
   - Find all changes from your last commit, complete rollback
   - Don't just change part, don't leave any residue
   - Don't use "fix later", "just use it for now" as excuses to keep wrong code
   - Forbidden: Stack new modifications on wrong code, trying to "fix"

3. **Found Original Design Has Problems → Directly Refactor, Don't Bypass**
   - If original architecture can't meet requirements, directly delete wrong design
   - Re-design correct architecture, then implement
   - Forbidden: Use various hacks, patches, special judgments to bypass design flaws

### III. Modification Principles (All Modifications Must Follow)

1. **Better to Rewrite Than Patch**
   - If a function/component has more than 3 bugs, directly delete and rewrite
   - If code needs more than 2 special judgments, directly delete and rewrite
   - If modification amount exceeds 50% of original code, directly delete and rewrite
   - Forbidden: Patch one after another on bad code

2. **Incremental Modification Must Be Based on Correct Existing Logic**
   - All new code must match existing code style
   - All new features must integrate into existing architecture, cannot be standalone
   - Forbidden: Introduce new design patterns, new dependencies, new code styles unless user explicitly requests

3. **Minimal Modification Principle**
   - Use minimal code to solve the problem
   - Don't add any features user didn't request
   - Don't do "pre-optimization", "reserve for future"
   - Forbidden: Write "comprehensive" generic solutions, only solve current specific problems

### IV. Code Quality Rules

1. **Absolutely No Garbage Code**
   - Delete all commented-out code
   - Delete all unused variables, functions, files
   - Delete all console.log, print and other debug code
   - Delete all TODO, FIXME comments, either solve or delete

2. **Must Match Existing Code Style Completely**
   - Naming conventions, indentation, spaces, line breaks must be exactly the same as existing code
   - Must use dependencies already introduced in the project, cannot add unnecessary dependencies
   - Must follow existing project directory structure and module division

3. **Must Handle All Edge Cases**
   - Null values, exceptions, error conditions must be handled
   - Cannot leave any code that might cause crashes
   - All async operations must have error handling

### V. Delivery and Acceptance Rules

1. **Each Delivery Must Be Complete and Runnable**
   - Cannot just give code snippets, must give complete files or complete functions
   - Must ensure code can run directly after copy-paste
   - Must test yourself first, confirm no syntax errors, no obvious bugs

2. **Must Explain Modification Scope and Impact**
   - Clearly state which files you modified
   - Clearly state what features your modification affects
   - Clearly state what operations user needs to do for it to take effect

3. **Must Self-Verify First**
   - Run code, confirm functionality is normal
   - Confirm original functionality isn't broken
   - Confirm no new bugs introduced

### VI. Absolutely Forbidden Behaviors (Violating Any One Requires Full Rewrite)

- ❌ Forbidden: Stack modifications on wrong code, trying to "fix"
- ❌ Forbidden: Leave any commented-out code, debug code, unused code
- ❌ Forbidden: Duplicate implement already existing functionality
- ❌ Forbidden: Modify parts user didn't request
- ❌ Forbidden: Fabricate non-existent metrics, data, effects
- ❌ Forbidden: Use "compat with old code" as excuse to keep wrong logic
- ❌ Forbidden: Introduce unnecessary dependencies, libraries, frameworks
- ❌ Forbidden: Do any "pre-optimization", "reserve for future" design
- ❌ Forbidden: Start modifying without understanding existing code
- ❌ Forbidden: Keep forcing solutions after finding you were wrong

### VII. Anti-Examples (Must Remember)

**❌ Wrong Approach:**
- Folding animation has white bar, just add `margin-top: -1px` to fix
- Recommendation persistence to JSON is wrong, just add frontend hiding logic
- Scroll lagging, just add `setTimeout` to delay execution
- Misunderstood requirement, keep changing on wrong basis trying to "align"

**✅ Correct Approach:**
- Delete entire wrong animation logic, rewrite synchronous transition
- Delete all recommendation write/read code, re-implement temporary display
- Delete entire lagging scroll implementation, rewrite smooth scroll based on requestAnimationFrame
- Delete all wrong code, re-confirm requirement and write from scratch

### VIII. Self-Check List After Each Modification

After writing code, must check against this list, all pass before delivery:

1. I completely read all related existing code
2. I confirmed this feature isn't duplicate implemented
3. I only modified files related to current task
4. I didn't leave any garbage code, debug code
5. My code style matches existing code completely
6. I ran the code myself, confirmed functionality is normal
7. I confirmed original functionality isn't broken
8. If I found previous modification was wrong, I already fully rolled back and rewrote correct code

---

## Local Development Environment Setup

### System Requirements

- Python 3.12+
- Node.js 22+
- pnpm (Frontend package manager)
- Docker (Optional, for infrastructure services)

### Backend Setup

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/LuomiNest.git
cd LuomiNest/backend

# Install dependencies (uv recommended)
pip install uv
uv sync --group dev

# Configure environment variables
cp config/.env.example config/.env
# Edit .env file, set necessary API Keys

# Start infrastructure services (optional)
docker compose -f ../docker/docker-compose.dev.yml up -d

# Run development server
uv run python main.py
```

### Frontend Setup

```bash
cd LuomiNest/frontend

# Install dependencies
pnpm install

# Run development server
pnpm dev

# Build production version
pnpm build
```

### TypeScript Type Checking

```bash
cd frontend

# Run type check
pnpm typecheck

# Or use vue-tsc directly
vue-tsc --noEmit -p tsconfig.web.json && vue-tsc --noEmit -p tsconfig.node.json
```

### Docker Development Environment (Recommended)

```bash
# Start complete development environment
cd LuomiNest/docker
docker compose -f docker-compose.dev.yml up -d

# Access the application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
```

## Project Structure

```
LuomiNest/
├── backend/                 # Python FastAPI backend
│   ├── app/                 # Application core code
│   │   ├── api/             # API routes and endpoints
│   │   ├── core/            # Core configuration and constants
│   │   ├── domains/         # Business domain logic
│   │   ├── engines/         # Engine modules (voice, render, memory, etc.)
│   │   ├── infrastructure/  # Infrastructure (database, MQTT, Redis)
│   │   ├── models/          # Data models
│   │   ├── runtime/         # Runtime platform adapters
│   │   ├── schemas/         # API Schema
│   │   ├── security/        # Security modules
│   │   └── services/        # Business services
│   ├── config/              # Configuration files
│   ├── scripts/             # Script tools
│   └── tests/               # Test code
│
├── frontend/                # Electron + Vue frontend
│   ├── src/                 # Source code
│   │   ├── main/            # Electron main process
│   │   ├── preload/         # Preload scripts
│   │   └── renderer/        # Vue render process
│   └── resources/           # Resource files
│
├── firmware/                # ESP32 firmware
│   ├── esp32-p4/            # ESP32-P4 main controller firmware
│   ├── esp32-s3/            # ESP32-S3 firmware
│   └── server/              # Live2D render server
│
├── docker/                  # Docker configuration
├── scripts/                 # Deployment and development scripts
└── .github/                 # GitHub configuration
```

## Pre-Commit Checks

### Backend Checks

```bash
cd backend

# Run tests
uv run pytest tests/

# Code format check
uv run ruff check app tests
uv run ruff format app tests

# Type check
uv run mypy app
```

### Frontend Checks

```bash
cd frontend

# Type check
pnpm typecheck

# Code format
pnpm format:write
```

## Coding Standards

### Python Code Standards

- Follow PEP 8 conventions
- Use type annotations (Type Hints)
- Use `async/await` for I/O operations
- Use Black formatter, line length 120
- Use absolute imports, avoid wildcard imports (`from x import *`)
- Functions and variables use snake_case
- Classes use PascalCase
- Constants use UPPER_SNAKE_CASE

### TypeScript/Vue Code Standards

- Use ES Modules (`import/export`)
- Prefer destructuring imports: `import { foo } from 'bar'`
- Use `const` for immutable variables, `let` for mutable
- Prefer arrow functions
- Components use PascalCase: `UserProfile.tsx`
- Utility functions use camelCase: `formatDate.ts`
- CSS class names use kebab-case: `user-profile`
- Add linear animations with `ease-in-out` for frontend

### Git Commit Standards

Commit message format: `<type>(<scope>): <subject>`

**Available types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation update
- `style`: Code format adjustment
- `refactor`: Code refactoring
- `test`: Test related
- `chore`: Build/tool related

**Examples:**
```
feat(voice): add Whisper ASR engine integration
fix(memory): handle empty session context
docs(api): update WebSocket API documentation
refactor(render)!: simplify Live2D model loader
```

## Branch Naming Standards

Recommended branch names:
- `feature/<short-name>` - New feature development
- `fix/<short-name>` - Bug fix
- `docs/<short-name>` - Documentation update
- `refactor/<short-name>` - Code refactoring

## Pull Request Requirements

Please include:
- Description of changes and reasons
- Related Issue (if any)
- Testing method and results
- Screenshots for UI changes (if applicable)

Keep PRs focused. Smaller PRs review faster.

## Report Bugs and Feature Requests

- Bug report: [Submit Bug Report](https://github.com/LuminousCX/LuomiNest/issues/new?template=bug_report.yaml)
- Feature request: [Submit Feature Request](https://github.com/LuminousCX/LuomiNest/issues/new?template=feature_request.yaml)

## Security Vulnerability Reporting

**Do not report security vulnerabilities in public Issues!**

Please report privately via email:
- Email: `luminouschenxi@outlook.com`
- Subject: `LuomiNest Security Report`

See: [Security Policy](SECURITY.md)

## License

By contributing, you agree your contributions will be licensed under the [GNU AGPL v3 License](LICENSE) used by this project.

## Get Help

- Check [Issues](https://github.com/LuminousCX/LuomiNest/issues)
- Join [Discussions](https://github.com/LuminousCX/LuomiNest/discussions)
- Read [Documentation](docs/)

---

Thank you for contributing to LuomiNest!