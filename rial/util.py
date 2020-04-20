import random
import string


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
