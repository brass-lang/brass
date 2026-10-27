from .ids import Role

SUPERVISOR_ONLY_UP_TO = 50_000
DIRECTOR_UP_TO = 500_000

STEP_ROLES = (Role.SUPERVISOR, Role.DIRECTOR, Role.FINANCE)


def steps_for(total: int) -> int:
    if total <= SUPERVISOR_ONLY_UP_TO:
        return 1
    if total <= DIRECTOR_UP_TO:
        return 2
    return 3


def role_for(step: int) -> Role:
    return STEP_ROLES[step - 1]
