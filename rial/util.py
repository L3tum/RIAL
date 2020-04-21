import hashlib
import random
import string
from typing import List

from llvmlite.ir import Function, MDValue, Module, Context

from rial.metadata.FunctionDefinition import FunctionDefinition


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


def _get_function_definition(self: Function) -> FunctionDefinition:
    md_value: MDValue = self.metadata['function_definition']
    return FunctionDefinition.from_mdvalue(md_value)


def _get_global_safe(self: Module, name: str):
    try:
        return self.get_global(name)
    except KeyError:
        return None


def _get_identified_type_if_exists(self: Context, name: str):
    if name in self.identified_types:
        return self.identified_types[name]
    return None


def _get_dependencies(self: Module) -> List[str]:
    mods = list()

    if 'dependencies' in self.namedmetadata:
        for op in self.get_named_metadata('dependencies').operands:
            mods.append(op.operands[0].string)

    return mods


def good_hash(w: str):
    return hashlib.md5(w.encode()).hexdigest()


def monkey_patch():
    Function.get_function_definition = _get_function_definition
    Module.get_global_safe = _get_global_safe
    Module.get_dependencies = _get_dependencies
    Context.get_identified_type_if_exists = _get_identified_type_if_exists
