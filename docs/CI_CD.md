# UK Compliance Platform — CI/CD Automation Guide

This guide details the automated build, test, and release validation pipelines configured via GitHub Actions.

## 1. Workflow Architecture
The pipeline is split into five distinct workflows under `.github/workflows/` to ensure isolated caching, fast runtimes, and clear step-level separation.

### I. Backend Pipeline (`backend.yml`)
Triggers on pushes or PRs targeting `backend/**` code paths.
- Setup python 3.12, install requirements, configure postgres + Redis test services in GitHub actions run layer.
- Runs `black --check` to enforce formatting.
- Runs `flake8` to enforce style linting rules.
- Runs `pytest --asyncio-mode=auto` to verify unit and regression suites.
- Generates coverage reports.

### II. Frontend Pipeline (`frontend.yml`)
Triggers on pushes or PRs targeting `frontend/**` code paths.
- Configures Node 20 runner, executes clean `npm ci` installs.
- Runs `npm run lint` validation.
- Runs TypeScript syntax type verification (`npx tsc --noEmit`).
- Performs Next.js build compilation (`npm run build`).

### III. Container Pipeline (`docker.yml`)
Triggers on docker/compose file alterations.
- Performs dry-run builds on frontend and backend Dockerfiles to verify multi-stage build layers compile cleanly.

### IV. Security Pipeline (`security.yml`)
Executes weekly and on code check-ins.
- Runs **Trivy** to scan workspace configuration manifests.
- Runs **Bandit** to check python code for common security bugs.
- Runs **Safety** and **pip-audit** to scan python dependency trees.
- Runs **npm audit** to check frontend packages.

### V. Release Deployment Pipeline (`deploy.yml`)
Triggers only when pushing tags starting with version prefix `v*` (e.g. `v16.0.0`).
- Performs build checks, logs into Enterprise Docker Registry, compiles optimized Docker production images, and pushes them to registries.
- Confirms Kubernetes context parameters, applies yaml manifest updates, and runs `kubectl rollout status` to verify deployment health.

---

## 2. Setting Up Pipeline Secret Variables
Ensure the following variables are configured under GitHub repository settings:
- `DOCKERHUB_USERNAME`: Enterprise container registry username.
- `DOCKERHUB_TOKEN`: Security registry login token.
- `KUBE_CONFIG_DATA`: Base64 encoded Kubernetes `kubeconfig` client profile.
- `CODECOV_TOKEN`: Coverage analyzer dashboard token.
