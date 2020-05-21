from typing import List, Tuple

from llvmlite import ir

from rial.LLVMGen import LLVMGen
from rial.ParserState import ParserState
from rial.builtin_type_to_llvm_mapper import is_builtin_type, map_shortcut_to_type
from rial.concept.TransformerInterpreter import TransformerInterpreter
from rial.concept.metadata_token import MetadataToken
from rial.concept.name_mangler import mangle_function_name
from rial.concept.parser import Tree, Token, Discard
from rial.log import log_fail
from rial.metadata.FunctionDefinition import FunctionDefinition
from rial.rial_types.RIALAccessModifier import RIALAccessModifier


class FunctionDeclarationTransformer(TransformerInterpreter):
    mangling: bool
    llvmgen: LLVMGen
    default_cc = "fastcc"

    def __init__(self):
        super().__init__()
        self.llvmgen = LLVMGen()
        self.mangling = True

    def attributed_func_decl(self, tree: Tree):
        nodes = tree.children
        attributes: List[Tree] = list()
        func_decl: Tree = None

        for node in nodes:
            if not isinstance(node, Tree):
                continue
            if node.data == "function_decl":
                func_decl = node
                break
            attributes.append(node)

        # TODO: Support actually implemented attributes
        for attribute in attributes:
            if attribute.children[0].value == "NoMangle":
                self.mangling = False

        func_decl = self.visit(func_decl)
        self.mangling = True
        return func_decl

    def external_function_decl(self, tree: Tree):
        nodes = tree.children
        access_modifier: RIALAccessModifier = nodes[0].access_modifier
        unsafe: bool = nodes[0].unsafe
        linkage = "external"
        calling_convention = "ccc"
        return_type = nodes[1].value
        name = nodes[2].value

        # External functions cannot be declared in a struct
        if self.llvmgen.current_struct is not None:
            log_fail(f"External function {name} cannot be declared inside a class!")
            raise Discard()

        args: List[Tuple[str, str]] = list()
        var_args = False
        i = 3
        while i < len(nodes):
            if var_args is True:
                log_fail("PARAMS must be last in arguments")
                break
            if nodes[i].type == "PARAMS":
                var_args = True
                i += 1
            if nodes[i].type == "IDENTIFIER":
                arg_type = nodes[i].value
                i += 1
                arg_name = nodes[i].value

                if var_args:
                    arg_name += "..."

                args.append((arg_type, arg_name))
                i += 1

        if not unsafe and not self.llvmgen.currently_unsafe:
            raise PermissionError("Can only declare external functions in unsafe blocks or as unsafe functions.")

        # Map RIAL args to llvm arg types
        llvm_args = [ParserState.map_type_to_llvm(arg[0]) for arg in args if not arg[1].endswith("...")]

        # Hasn't been declared previously, redeclare the function type here
        llvm_return_type = ParserState.map_type_to_llvm(return_type)
        func_type = self.llvmgen.create_function_type(llvm_return_type, llvm_args, var_args)

        # Create the actual function in IR
        func = self.llvmgen.create_function_with_type(name, name, func_type, linkage,
                                                      calling_convention,
                                                      list(map(lambda arg: arg[1], args)),
                                                      FunctionDefinition(return_type, access_modifier, args, "",
                                                                         unsafe))

        raise Discard()

    def extension_function_decl(self, tree: Tree):
        nodes = tree.children
        access_modifier: RIALAccessModifier = nodes[0].access_modifier
        unsafe: bool = nodes[0].unsafe
        linkage = access_modifier.get_linkage()
        calling_convention = self.default_cc
        return_type = nodes[1].value
        name = nodes[2].value

        # Extension functions cannot be declared inside other classes.
        if self.llvmgen.current_struct is not None:
            log_fail(f"Extension function {name} cannot be declared inside another class!")
            raise Discard()

        if not self.mangling:
            log_fail(f"Extension function {name} does not qualify for no mangling.")
            raise Discard()

        args: List[Tuple[str, str]] = list()
        this_arg = map_shortcut_to_type(nodes[3].value)
        has_body = False

        args.append((nodes[3].value, nodes[4].value))

        i = 5
        while i < len(nodes):
            if not isinstance(nodes[i], Token):
                has_body = True
                break
            if nodes[i].type == "IDENTIFIER":
                arg_type = nodes[i].value
                i += 1
                arg_name = nodes[i].value
                args.append((arg_type, arg_name))
                i += 1
            else:
                break

        # Map RIAL args to llvm arg types
        llvm_args = [ParserState.map_type_to_llvm(arg[0]) for arg in args if not arg[1].endswith("...")]

        full_function_name = mangle_function_name(name, llvm_args, this_arg)
        full_function_name = f"{ParserState.module().name}:{full_function_name}"

        # Hasn't been declared previously, redeclare the function type here
        llvm_return_type = ParserState.map_type_to_llvm(return_type)
        func_type = self.llvmgen.create_function_type(llvm_return_type, llvm_args, False)

        # Create the actual function in IR
        func = self.llvmgen.create_function_with_type(full_function_name, name, func_type, linkage,
                                                      calling_convention,
                                                      list(map(lambda arg: arg[1], args)),
                                                      FunctionDefinition(return_type, access_modifier, args,
                                                                         self.llvmgen.current_struct is not None and self.llvmgen.current_struct.name or "",
                                                                         unsafe))

        if is_builtin_type(this_arg):
            if this_arg not in ParserState.builtin_types:
                ParserState.builtin_types[this_arg] = dict()

            ParserState.builtin_types[this_arg][func.name] = func

            if not this_arg in ParserState.module().builtin_type_methods:
                ParserState.module().builtin_type_methods[this_arg] = list()
            ParserState.module().builtin_type_methods[this_arg].append(func.name)
        else:
            struct = ParserState.find_struct(this_arg)

            if struct is None:
                log_fail(f"Extension function for non-existing type {this_arg}")
                ParserState.module().functions.remove(func)
                raise Discard()

            struct.definition.functions.append(func.name)

        if not has_body:
            raise Discard()

        token = nodes[2]
        metadata_token = MetadataToken(token.type, token.value)
        metadata_token.metadata["full_name"] = full_function_name
        metadata_token.metadata["body_start"] = i
        metadata_token.metadata['rial_arg_types'] = [arg[0] for arg in args]
        nodes.remove(token)
        nodes.insert(0, metadata_token)

        return Tree('function_decl', nodes)

    def function_decl(self, tree: Tree):
        nodes = tree.children

        # Function specialisation
        if isinstance(nodes[0], Tree):
            return self.visit(nodes[0])

        access_modifier: RIALAccessModifier = nodes[0].access_modifier
        unsafe: bool = nodes[0].unsafe
        linkage = access_modifier.get_linkage()
        main_function = False
        calling_convention = self.default_cc
        return_type = nodes[1].value
        name = nodes[2].value

        args: List[Tuple[str, str]] = list()

        i = 3
        has_body = False

        while i < len(nodes):
            if not isinstance(nodes[i], Token):
                has_body = True
                break
            if nodes[i].type == "IDENTIFIER":
                arg_type = nodes[i].value
                i += 1
                arg_name = nodes[i].value
                args.append((arg_type, arg_name))
                i += 1
            else:
                break

        # Map RIAL args to llvm arg types
        llvm_args = [ParserState.map_type_to_llvm(arg[0]) for arg in args if not arg[1].endswith("...")]

        # Add class as implicit self parameter
        if self.llvmgen.current_struct is not None:
            llvm_args.insert(0, ir.PointerType(self.llvmgen.current_struct))
            args.insert(0, (self.llvmgen.current_struct.name, "this"))

        # If the function has the NoMangleAttribute we need to use the normal name
        if not self.mangling:
            full_function_name = name
        else:
            if self.llvmgen.current_struct is not None:
                full_function_name = mangle_function_name(name, llvm_args,
                                                          self.llvmgen.current_struct.name)
            else:
                full_function_name = mangle_function_name(name, llvm_args)
                full_function_name = f"{ParserState.module().name}:{full_function_name}"

        # Check if main method
        if full_function_name.endswith("main:main") and full_function_name.count(':') == 2:
            main_function = True

            # Check that main method returns either Int32 or void
            if return_type != "Int32" and return_type != "void":
                log_fail(f"Main method must return an integer status code or void, {return_type} given!")

        # Search for function in the archives
        # func = ParserState.search_function(full_function_name)

        # Function has been previously declared in other module
        # if func is not None and (func.module.name != ParserState.module().name or not func.is_declaration):
        #     # Check if either:
        #     # - has no body (cannot redeclare functions) or
        #     # - is already implemented and
        #     #   - is either public or
        #     #     - internal and
        #     #     - is in same package (cannot reimplement functions)
        #     # TODO: LLVM checks this anyways but maybe we wanna do it, too?
        #     log_fail(f"Function {full_function_name} already declared elsewhere")
        #     raise Discard()

        # Hasn't been declared previously, redeclare the function type here
        llvm_return_type = ParserState.map_type_to_llvm(return_type)
        func_type = self.llvmgen.create_function_type(llvm_return_type, llvm_args, False)

        # Create the actual function in IR
        func = self.llvmgen.create_function_with_type(full_function_name, name, func_type, linkage,
                                                      calling_convention,
                                                      list(map(lambda arg: arg[1], args)),
                                                      FunctionDefinition(return_type, access_modifier, args,
                                                                         self.llvmgen.current_struct is not None and self.llvmgen.current_struct.name or "",
                                                                         unsafe))

        if self.llvmgen.current_struct is not None:
            self.llvmgen.current_struct.definition.functions.append(func.name)

        # Always inline the main function into the compiler supplied one
        if main_function:
            func.attributes.add('alwaysinline')

        # If it has no body we do not need to go through it later as it's already declared with this method.
        if not has_body:
            raise Discard()

        token = nodes[2]
        metadata_token = MetadataToken(token.type, token.value)
        metadata_token.metadata["full_name"] = full_function_name
        metadata_token.metadata["body_start"] = i
        metadata_token.metadata['rial_arg_types'] = [arg[0] for arg in args]
        nodes.remove(token)
        nodes.insert(0, metadata_token)

        return Tree('function_decl', nodes)
