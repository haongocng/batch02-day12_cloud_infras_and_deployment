"""Production readiness checker for the Day 12 final project."""

from __future__ import annotations

import os
import sys


def check(name: str, passed: bool, detail: str = "") -> dict[str, bool]:
    icon = "[OK]" if passed else "[FAIL]"
    suffix = f" - {detail}" if detail else ""
    print(f"  {icon} {name}{suffix}")
    return {"name": name, "passed": passed}


def _read(path: str) -> str:
    with open(path, encoding="utf-8", errors="ignore") as file:
        return file.read()


def run_checks() -> bool:
    results: list[dict[str, bool]] = []
    base = os.path.dirname(__file__)

    print("\n" + "=" * 55)
    print("  Production Readiness Check - Day 12 Lab")
    print("=" * 55)

    print("\nRequired Files")
    results.append(check("Dockerfile exists", os.path.exists(os.path.join(base, "Dockerfile"))))
    results.append(check("docker-compose.yml exists", os.path.exists(os.path.join(base, "docker-compose.yml"))))
    results.append(check(".dockerignore exists", os.path.exists(os.path.join(base, ".dockerignore"))))
    results.append(check(".env.example exists", os.path.exists(os.path.join(base, ".env.example"))))
    results.append(check("requirements.txt exists", os.path.exists(os.path.join(base, "requirements.txt"))))
    results.append(
        check(
            "railway.toml or render.yaml exists",
            os.path.exists(os.path.join(base, "railway.toml"))
            or os.path.exists(os.path.join(base, "render.yaml")),
        )
    )

    print("\nSecurity")
    gitignore = os.path.join(base, ".gitignore")
    root_gitignore = os.path.join(base, "..", ".gitignore")
    env_ignored = False
    for candidate in [gitignore, root_gitignore]:
        if os.path.exists(candidate) and ".env" in _read(candidate):
            env_ignored = True
            break
    results.append(check(".env in .gitignore", env_ignored, "Add .env to .gitignore!" if not env_ignored else ""))

    secrets_found: list[str] = []
    for relative_path in ["app/main.py", "app/config.py"]:
        file_path = os.path.join(base, relative_path)
        if os.path.exists(file_path):
            content = _read(file_path)
            for marker in ["sk-", "password123", "hardcoded"]:
                if marker in content:
                    secrets_found.append(f"{relative_path}:{marker}")
    results.append(check("No hardcoded secrets in code", not secrets_found, str(secrets_found) if secrets_found else ""))

    print("\nAPI Endpoints (code check)")
    main_py = os.path.join(base, "app", "main.py")
    if os.path.exists(main_py):
        content = _read(main_py)
        results.append(check("/health endpoint defined", '"/health"' in content or "'/health'" in content))
        results.append(check("/ready endpoint defined", '"/ready"' in content or "'/ready'" in content))
        results.append(check("Authentication implemented", "api_key" in content.lower() or "verify_token" in content))
        results.append(check("Rate limiting implemented", "rate_limit" in content.lower() or "429" in content))
        results.append(check("Graceful shutdown (SIGTERM)", "SIGTERM" in content))
        results.append(check("Structured logging (JSON)", "json.dumps" in content or '"event"' in content))
    else:
        results.append(check("app/main.py exists", False, "Create app/main.py"))

    print("\nDocker")
    dockerfile = os.path.join(base, "Dockerfile")
    if os.path.exists(dockerfile):
        content = _read(dockerfile)
        results.append(check("Multi-stage build", "AS builder" in content and "AS runtime" in content))
        results.append(check("Non-root user", "useradd" in content and "USER " in content))
        results.append(check("HEALTHCHECK instruction", "HEALTHCHECK" in content))
        results.append(check("Slim base image", "slim" in content or "alpine" in content))

    dockerignore = os.path.join(base, ".dockerignore")
    if os.path.exists(dockerignore):
        content = _read(dockerignore)
        results.append(check(".dockerignore covers .env", ".env" in content))
        results.append(check(".dockerignore covers __pycache__", "__pycache__" in content))

    passed = sum(1 for result in results if result["passed"])
    total = len(results)
    pct = round(passed / total * 100)

    print("\n" + "=" * 55)
    print(f"  Result: {passed}/{total} checks passed ({pct}%)")
    if pct == 100:
        print("  PRODUCTION READY")
    elif pct >= 80:
        print("  Almost there. Fix the failed items above.")
    elif pct >= 60:
        print("  Good progress. Several items need attention.")
    else:
        print("  Not ready. Review the checklist carefully.")
    print("=" * 55 + "\n")
    return pct == 100


if __name__ == "__main__":
    sys.exit(0 if run_checks() else 1)
