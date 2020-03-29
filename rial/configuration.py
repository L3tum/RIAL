from pathlib import Path


class Configuration:
    project_name: str
    source_path: Path
    cache_path: Path
    bin_path: Path

    def __init__(self, project_name: str, source_path: Path, cache_path: Path, bin_path: Path):
        self.project_name = project_name
        self.source_path = source_path
        self.cache_path = cache_path
        self.bin_path = bin_path
