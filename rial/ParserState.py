import threading
from typing import Dict, Optional, List, Tuple

from llvmlite import ir
from llvmlite.ir import Module, Function

from rial.LLVMFunction import LLVMFunction
from rial.LLVMStruct import LLVMStruct
from rial.builtin_type_to_llvm_mapper import map_type_to_llvm
from rial.compilation_manager import CompilationManager
from rial.log import log_fail
from rial.rial_types.RIALAccessModifier import RIALAccessModifier


class ParserState:
    functions: Dict[str, LLVMFunction]
    implemented_functions: List[str]
    structs: Dict[str, LLVMStruct]
    main_function: LLVMFunction
    threadLocalUsings: threading.local
    threadLocalModule: threading.local

    def __init__(self):
        raise PermissionError()

    @staticmethod
    def init():
        ParserState.functions = dict()
        ParserState.implemented_functions = list()
        ParserState.structs = dict()
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
    def search_function(name: str) -> Optional[LLVMFunction]:
        if name in ParserState.functions:
            return ParserState.functions[name]

        return None

    @staticmethod
    def search_implemented_functions(name: str) -> bool:
        return name in ParserState.implemented_functions

    @staticmethod
    def search_structs(name: str) -> Optional[LLVMStruct]:
        if name in ParserState.structs:
            return ParserState.structs[name]

        return None

    @staticmethod
    def find_function(full_function_name: str) -> Optional[Function]:
        # Try to find function in current module
        func = next((func for func in ParserState.module().functions if func.name == full_function_name), None)

        # Try to find function in current module with module specifier
        if func is None:
            func = next((func for func in ParserState.module().functions if
                         func.name == f"{ParserState.module().name}:{full_function_name}"), None)

        # If func isn't in current module
        if func is None:
            # Try to find function by full name
            llvm_function = ParserState.search_function(full_function_name)

            # If couldn't find it, iterate through usings and try to find function
            if llvm_function is None:
                functions_found: List[Tuple[str, LLVMFunction]] = list()

                for use in ParserState.usings():
                    llvm_function = ParserState.search_function(f"{use}:{full_function_name}")
                    if llvm_function is None:
                        continue
                    functions_found.append((use, llvm_function,))

                if len(functions_found) > 1:
                    log_fail(f"Function {full_function_name} has been declared multiple times!")
                    log_fail(f"Specify the specific function to use by adding the namespace to the function call")
                    log_fail(f"E.g. {functions_found[0][0]}:{full_function_name}()")
                    return None

                # Check for number of functions found
                if len(functions_found) == 1:
                    llvm_function = functions_found[0][1]

            if llvm_function is not None:
                # Function cannot be accessed if:
                #   - Function is not public and
                #   - Function is internal but not in same TLM (top level module) or
                #   - Function is private but not in same module
                if llvm_function.access_modifier != RIALAccessModifier.PUBLIC and \
                        ((llvm_function.access_modifier == RIALAccessModifier.INTERNAL and
                          llvm_function.module.split(':')[0] != ParserState.module().name.split(':')[0]) or
                         (llvm_function.access_modifier == RIALAccessModifier.PRIVATE and
                          llvm_function.module != ParserState.module().name)):
                    log_fail(
                        f"Cannot access method {full_function_name} in module {llvm_function.module}!")
                    return None

                # Check if it has been declared previously (by another function call for example)
                func = next((func for func in ParserState.module().functions if
                             func.name == llvm_function.name), None)

                # Declare function if not declared in current module
                if func is None:
                    func = ir.Function(ParserState.module(), llvm_function.function_type, name=llvm_function.name)

        # Try request the module that the function might(!) be in
        if func is None:
            true_function_name = full_function_name.split('.')[0]
            if ":" in true_function_name:
                mod_name = ':'.join(true_function_name.split(':')[0:-1])

                # Check that the module hasn't been compiled yet
                if not CompilationManager.check_module_already_compiled(mod_name):
                    CompilationManager.request_module(mod_name)
                    return ParserState.find_function(full_function_name)

        return func

    @staticmethod
    def find_struct(struct_name: str):
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

        # Struct cannot be accessed if:
        #   - Struct is not public and
        #   - Struct is internal but not in same TLM (top level module) or
        #   - Struct is private but not in same module
        if struct.access_modifier != RIALAccessModifier.PUBLIC and \
                ((struct.access_modifier == RIALAccessModifier.INTERNAL and
                  struct.module_name.split(':')[0] != ParserState.module().name.split(':')[0]) or
                 (struct.access_modifier == RIALAccessModifier.PRIVATE and
                  struct.module_name != ParserState.module().name)):
            log_fail(
                f"Cannot access struct {struct_name} in module {struct.module_name}!")
            return None

        return struct

    @staticmethod
    def map_type_to_llvm(name: str):
        llvm_type = map_type_to_llvm(name)

        # Check if builtin type
        if llvm_type is None:
            llvm_struct = ParserState.find_struct(name)

            if llvm_struct is not None:
                llvm_type = llvm_struct.struct
            else:
                log_fail(f"Referenced unknown type {name}")
                return None

        return llvm_type
