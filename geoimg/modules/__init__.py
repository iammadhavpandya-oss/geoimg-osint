"""Optional analysis modules. Each module must degrade gracefully when its
dependencies, binaries or API keys are missing: return {"status": "skipped", "reason": ...}."""


def skipped(reason: str, **extra):
    d = {"status": "skipped", "reason": reason}
    d.update(extra)
    return d
