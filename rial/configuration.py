from pathlib import Path
from typing import Any


class Configuration:
    project_name: str
    source_path: Path
    cache_path: Path
    bin_path: Path
    raw_opts: Any
    rial_path: Path

    def __init__(self, project_name: str, source_path: Path, cache_path: Path, bin_path: Path, rial_path: Path,
                 raw_opts: Any):
        self.project_name = project_name
        self.source_path = source_path
        self.cache_path = cache_path
        self.bin_path = bin_path
        self.rial_path = rial_path
        self.raw_opts = raw_opts
