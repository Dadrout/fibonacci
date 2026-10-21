from contextvars import ContextVar

generation_id: ContextVar[str] = ContextVar("generation_id", default="untracked")
