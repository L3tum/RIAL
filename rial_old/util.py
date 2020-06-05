import hashlib
import random
import string

from llvmlite.ir import Context


def generate_random_name(count: int):
    return ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=count))


def rreplace(s, old, new, occurrence=-1):
    li = s.rsplit(old, occurrence)
    return new.join(li)


def pythonify(data: dict):
    for key, value in data.items():
        if isinstance(value, dict):
            value = pythonify(value)
        elif isinstance(value, list):
            value = [pythonify(val) for val in value]
        elif isinstance(value, str):
            if value.lower() == "true":
                value = True
            elif value.lower() == "false":
                value = False
        data[key] = value

    return data


def good_hash(w: str):
    return hashlib.md5(w.encode()).hexdigest()


def _get_identified_type_if_exists(self: Context, name: str):
    if name in self.identified_types:
        return self.identified_types[name]
    return None


def monkey_patch():
    Context.get_identified_type_if_exists = _get_identified_type_if_exists
