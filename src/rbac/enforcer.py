import casbin
from pathlib import Path

_RBAC_DIR = Path(__file__).parent
_enforcer: casbin.Enforcer | None = None


def get_enforcer() -> casbin.Enforcer:
    global _enforcer
    if _enforcer is None:
        _enforcer = casbin.Enforcer(
            str(_RBAC_DIR / "model.conf"),
            str(_RBAC_DIR / "policy.csv"),
        )
    return _enforcer
