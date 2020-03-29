from contextlib import contextmanager
from enum import Enum
from typing import List
from timeit import default_timer as timer


class ExecutionStep(Enum):
    INIT = "Initializing the compiler and dependencies"
    SCAN_DIR = "Scanning directory for contents"
    READ_FILE = "Reading file into memory for processing"
    PARSE_FILE = "Lexing and parsing file into an AST"
    COMPILE_MOD = "Compile the file into a module"
    COMPILE_OBJ = "Compile module into object file"
    WRITE_OBJ = "Write out the object file"
    LINK_EXE = "Link all object files together into an exe"


class ExecutionEvent:
    file: str
    time_taken_seconds: float
    step: ExecutionStep

    def __init__(self, file: str, time_taken_seconds: float, step: ExecutionStep):
        self.file = file
        self.time_taken_seconds = time_taken_seconds
        self.step = step

    def __str__(self):
        return f"{self.step} : {self.time_taken_seconds.__round__(3)}s {self.file}"


execution_events: List[ExecutionEvent] = list()

profiling: bool = False


def set_profiling(profile: bool):
    global profiling
    profiling = profile


@contextmanager
def run_with_profiling(file: str, step: ExecutionStep):
    start = 0
    if profiling:
        start = timer()
    yield
    if profiling:
        end = timer()
        execution_events.append(ExecutionEvent(file, (end - start), step))
