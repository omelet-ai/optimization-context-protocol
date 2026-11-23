"""Generate and verify independent server projects from the installed template."""
from .scaffold import create_project, strip_content, inject_content

__all__ = ["create_project", "strip_content", "inject_content"]
