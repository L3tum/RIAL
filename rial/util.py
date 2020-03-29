import string
import random


def generate_random_name(count: int):
    return ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=count))


def rreplace(s, old, new, occurrence=-1):
    li = s.rsplit(old, occurrence)
    return new.join(li)


def _path_from_mod_name(project_name: str, source_path: str, mod_name: str) -> str:
    mod_name = mod_name.replace(':', '/') + ".rial"

    if mod_name.startswith(project_name):
        mod_name = mod_name.replace(project_name, source_path)

    return mod_name


def _mod_name_from_path(path: str) -> str:
    s = path.strip('/').replace('.rial', '').replace('/', ':')
    return s
