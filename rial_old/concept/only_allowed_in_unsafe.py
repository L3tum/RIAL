from contextlib import contextmanager

from rial.ParserState import ParserState


@contextmanager
def only_allowed_in_unsafe():
    if not ParserState.llvmgen().currently_unsafe:
        raise PermissionError()
