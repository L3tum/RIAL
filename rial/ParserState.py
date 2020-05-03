import threading
from typing import Optional, List, Tuple, Dict

from llvmlite import ir
from llvmlite.ir import Function

from rial.builtin_type_to_llvm_mapper import map_type_to_llvm
from rial.compilation_manager import CompilationManager
from rial.log import log_fail
from rial.metadata.FunctionDefinition import FunctionDefinition
from rial.metadata.RIALFunction import RIALFunction
from rial.metadata.RIALIdentifiedStructType import RIALIdentifiedStructType
from rial.metadata.RIALModule import RIALModule
from rial.rial_types.RIALAccessModifier import RIALAccessModifier


class ParserState:
    cached_functions: Dict[str, RIALFunction]
    cached_struct_modules: Dict[str, RIALModule]
    implemented_functions: List[str]
    threadLocalUsings: threading.local
    threadLocalModule: threading.local
    builtin_types: Dict[str, Dict[str, RIALFunction]]

    def __init__(self):
        raise PermissionError()

    @staticmethod
    def init():
        ParserState.implemented_functions = list()
        ParserState.threadLocalUsings = threading.local()
        ParserState.threadLocalModule = threading.local()
        ParserState.cached_functions = dict()
        ParserState.cached_struct_modules = dict()
        ParserState.builtin_types = dict()

    @staticmethod
    def reset_usings():
        ParserState.threadLocalUsings.usings = list()

    @staticmethod
    def set_module(module: RIALModule):
        ParserState.threadLocalModule.module = module

    @classmethod
    def usings(cls) -> List[str]:
        return cls.threadLocalUsings.usings

    @classmethod
    def module(cls) -> RIALModule:
        return cls.threadLocalModule.module

    @staticmethod
    def search_function(name: str) -> Optional[RIALFunction]:
        # Check if cached
        if name in ParserState.cached_functions:
            return ParserState.cached_functions[name]

        # Check if in current module
        func = ParserState.module().get_global_safe(name)

        if func is None:
            mods = dict(CompilationManager.modules)

            for key, mod in mods.items():
                func = mod.get_global_safe(name)

                if func is not None:
                    break

        if func is not None:
            ParserState.cached_functions[name] = func

        return func

    @staticmethod
    def search_structs(name: str) -> Optional[RIALIdentifiedStructType]:
        # Does a global search.
        return ParserState.module().context.get_identified_type_if_exists(name)

    @staticmethod
    def find_function(full_function_name: str) -> Optional[RIALFunction]:
        # Try to find function in current module
        func = ParserState.module().get_global_safe(full_function_name)

        # Try to find function in current module with module specifier
        if func is None:
            func = ParserState.module().get_global_safe(f"{ParserState.module().name}:{full_function_name}")

        # If func isn't in current module
        if func is None:
            # Try to find function by full name
            func = ParserState.search_function(full_function_name)

            # If couldn't find it, iterate through usings and try to find function
            if func is None:
                functions_found: List[Tuple[str, Function]] = list()

                for use in ParserState.usings():
                    function = ParserState.search_function(f"{use}:{full_function_name}")
                    if function is None:
                        continue
                    functions_found.append((use, function,))

                if len(functions_found) > 1:
                    log_fail(f"Function {full_function_name} has been declared multiple times!")
                    log_fail(f"Specify the specific function to use by adding the namespace to the function call")
                    log_fail(f"E.g. {functions_found[0][0]}:{full_function_name}()")
                    return None

                # Check for number of functions found
                if len(functions_found) == 1:
                    func = functions_found[0][1]

            if func is not None:
                # Function is in current module and only a declaration, safe to assume that it's a redeclared function
                # from another module or originally declared in this module anyways
                if func.module.name != ParserState.module().name and not func.is_declaration:
                    # Function cannot be accessed if:
                    #   - Function is not public and
                    #   - Function is internal but not in same TLM (top level module) or
                    #   - Function is private but not in same module
                    func_def: FunctionDefinition = func.definition
                    if func_def.access_modifier != RIALAccessModifier.PUBLIC and \
                            ((func_def.access_modifier == RIALAccessModifier.INTERNAL and
                              func.module.name.split(':')[0] != ParserState.module().name.split(':')[0]) or
                             (func_def.access_modifier == RIALAccessModifier.PRIVATE and
                              func.module.name != ParserState.module().name)):
                        log_fail(
                            f"Cannot access method {full_function_name} in module {func.module.name}!")
                        return None

        return func

    @staticmethod
    def find_struct(struct_name: str) -> Optional[RIALIdentifiedStructType]:
        # Search with name
        struct = ParserState.search_structs(struct_name)

        # Search with current module specifier
        if struct is None:
            struct = ParserState.search_structs(f"{ParserState.module().name}:{struct_name}")

        # Iterate through usings
        if struct is None:
            structs_found: List[Tuple] = list()
            for using in ParserState.usings():
                s = ParserState.search_structs(f"{using}:{struct_name}")

                if s is not None:
                    structs_found.append((using, s))
            if len(structs_found) == 0:
                return None

            if len(structs_found) > 1:
                log_fail(f"Multiple declarations found for {struct_name}")
                log_fail(f"Specify one of them by using {structs_found[0][0]}:{struct_name} for example")
                return None
            struct = structs_found[0][1]

        return struct

    @staticmethod
    def map_type_to_llvm(name: str):
        llvm_type = map_type_to_llvm(name)

        # Check if builtin type
        if llvm_type is None:
            struct = ParserState.find_struct(name)

            if struct is not None:
                llvm_type = ir.PointerType(struct)
            else:
                log_fail(f"Referenced unknown type {name}")
                return None

        return llvm_type

    @staticmethod
    def map_type_to_llvm_no_pointer(name: str):
        llvm_type = map_type_to_llvm(name)

        # Check if builtin type
        if llvm_type is None:
            llvm_type = ParserState.find_struct(name)

            if llvm_type is None:
                log_fail(f"Referenced unknown type {name}")
                return None

        return llvm_type
