import random
import string

from llvmlite.ir import Function, MDValue, Module

from rial.rial_types.RIALAccessModifier import RIALAccessModifier


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


def _get_access_modifier(self: Function):
    md_value: MDValue = self.metadata['function_definition']
    return RIALAccessModifier(md_value.operands[1].string)


def _get_global_safe(self: Module, name: str):
    try:
        return self.get_global(name)
    except KeyError:
        return None


def monkey_patch():
    Function.get_access_modifier = _get_access_modifier
    Module.get_global_safe = _get_global_safe
