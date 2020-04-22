import threading
from typing import Optional, List, Tuple

from llvmlite import ir
from llvmlite.ir import Module, Function, IdentifiedStructType

from rial.builtin_type_to_llvm_mapper import map_type_to_llvm
from rial.compilation_manager import CompilationManager
from rial.log import log_fail
from rial.metadata.FunctionDefinition import FunctionDefinition
from rial.metadata.StructDefinition import StructDefinition
from rial.rial_types.RIALAccessModifier import RIALAccessModifier


class ParserState:
    implemented_functions: List[str]
    threadLocalUsings: threading.local
    threadLocalModule: threading.local

    def __init__(self):
        raise PermissionError()

    @staticmethod
    def init():
        ParserState.implemented_functions = list()
        ParserState.threadLocalUsings = threading.local()
        ParserState.threadLocalModule = threading.local()

    @staticmethod
    def reset_usings():
        ParserState.threadLocalUsings.usings = list()

    @staticmethod
    def set_module(module: Module):
        ParserState.threadLocalModule.module = module

    @classmethod
    def usings(cls) -> List[str]:
        return cls.threadLocalUsings.usings

    @classmethod
    def module(cls) -> Module:
        return cls.threadLocalModule.module

    @staticmethod
    def search_function(name: str) -> Optional[Function]:
        # Check if in current module
        func = ParserState.module().get_global_safe(name)

        if func is not None:
            return func

        mods = dict(CompilationManager.modules)

        for key, mod in mods.items():
            func = mod.get_global_safe(name)

            if func is not None:
                return func

        return None

    @staticmethod
    def search_structs(name: str) -> Optional[IdentifiedStructType]:
        # Does a global search. We then need to find the module it's actually defined in.
        ty = ParserState.module().context.get_identified_type_if_exists(name)

        if ty is None:
            return None

        if hasattr(ty, 'module'):
            return ty

        # Check if in current module
        try:
            ParserState.module().get_named_metadata(f"{ty.name.replace(':', '_')}.definition")
            ty.module = ParserState.module()

            return ty
        except KeyError:
            pass

        mods = dict(CompilationManager.modules)

        for key, mod in mods.items():
            try:
                mod.get_named_metadata(f"{ty.name.replace(':', '_')}.definition")
                ty.module = mod

                return ty
            except KeyError:
                pass

        if not hasattr(ty, 'module'):
            return None
        return ty

    @staticmethod
    def find_function(full_function_name: str) -> Optional[Function]:

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
                    func_def: FunctionDefinition = func.get_function_definition()
                    if func_def.access_modifier != RIALAccessModifier.PUBLIC and \
                            ((func_def.access_modifier == RIALAccessModifier.INTERNAL and
                              func.module.name.split(':')[0] != ParserState.module().name.split(':')[0]) or
                             (func_def.access_modifier == RIALAccessModifier.PRIVATE and
                              func.module.name != ParserState.module().name)):
                        log_fail(
                            f"Cannot access method {full_function_name} in module {func.module.name}!")
                        return None

        # Try request the module that the function might(!) be in
        if func is None:
            true_function_name = full_function_name.split('.')[0]
            if ":" in true_function_name:
                mod_name = ':'.join(true_function_name.split(':')[0:-1])

                # Check that the module hasn't been compiled yet
                if not CompilationManager.check_module_already_compiled(mod_name):
                    ParserState.module().add_named_metadata('dependencies', (mod_name,))
                    CompilationManager.request_module(mod_name)
                    return ParserState.find_function(full_function_name)

        return func

    @staticmethod
    def find_struct(struct_name: str) -> Optional[IdentifiedStructType]:
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

        # Get metadata for struct
        struct_def = StructDefinition.from_mdvalue(
            struct.module.get_named_metadata(f"{struct.name.replace(':', '_')}.definition"))

        # Struct cannot be accessed if:
        #   - Struct is not public and
        #   - Struct is internal but not in same TLM (top level module) or
        #   - Struct is private but not in same module
        if struct_def.access_modifier != RIALAccessModifier.PUBLIC and \
                ((struct_def.access_modifier == RIALAccessModifier.INTERNAL and
                  struct.module.name.split(':')[0] != ParserState.module().name.split(':')[0]) or
                 (struct_def.access_modifier == RIALAccessModifier.PRIVATE and
                  struct.module.name != ParserState.module().name)):
            log_fail(
                f"Cannot access struct {struct_name} in module {struct.module.name}!")
            return None

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
