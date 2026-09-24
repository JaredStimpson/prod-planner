class PlannerError(Exception):
    """A user-correctable planner error."""


class ValidationError(PlannerError):
    """Input data failed validation."""

