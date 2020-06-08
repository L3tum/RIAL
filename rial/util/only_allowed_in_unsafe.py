from contextlib import contextmanager

from rial.compilation_manager import CompilationManager


@contextmanager
def only_allowed_in_unsafe(context: str = ""):
    if not CompilationManager.current_module.currently_unsafe:
        raise PermissionError(context)
    yield
