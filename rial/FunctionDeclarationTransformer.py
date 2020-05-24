from typing import List

from rial.LLVMGen import LLVMGen
from rial.ParserState import ParserState
from rial.builtin_type_to_llvm_mapper import map_shortcut_to_type
from rial.concept.TransformerInterpreter import TransformerInterpreter
from rial.concept.metadata_token import MetadataToken
from rial.concept.name_mangler import mangle_function_name
from rial.concept.parser import Tree, Token, Discard
from rial.log import log_fail
from rial.metadata.FunctionDefinition import FunctionDefinition
from rial.rial_types.RIALAccessModifier import RIALAccessModifier
from rial.rial_types.RIALVariable import RIALVariable


class FunctionDeclarationTransformer(TransformerInterpreter):
    mangling: bool
    llvmgen: LLVMGen
    default_cc = "fastcc"

    def __init__(self):
        super().__init__()
        self.llvmgen = ParserState.llvmgen()
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

        # TODO: Refactor into own tree as well
        args: List[RIALVariable] = list()
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

                arg = RIALVariable(arg_name, arg_type)

                args.append(arg)
                i += 1

        if not unsafe and not self.llvmgen.currently_unsafe:
            raise PermissionError("Can only declare external functions in unsafe blocks or as unsafe functions.")

        # Create func type
        llvm_args = [arg.llvm_type_as_function_arg for arg in args if not arg.name.endswith("...")]
        llvm_return_type = ParserState.map_type_to_llvm(return_type)
        func_type = self.llvmgen.create_function_type(llvm_return_type, llvm_args, var_args)

        # Create the actual function in IR
        func = self.llvmgen.create_function_with_type(name, name, func_type, linkage,
                                                      calling_convention,
                                                      FunctionDefinition(return_type, access_modifier, args,
                                                                         unsafe=unsafe))

        # Update the backing values
        for i in range(len(func.args)):
            func.definition.rial_args[i].backing_value = func.args[i]

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

        args: List[RIALVariable] = list()
        this_arg = map_shortcut_to_type(nodes[3].value)
        has_body = False

        args.append(RIALVariable(nodes[4].value, nodes[3].value))

        i = 5
        while i < len(nodes):
            if not isinstance(nodes[i], Token):
                has_body = True
                break
            if nodes[i].type == "IDENTIFIER":
                arg_type = nodes[i].value
                i += 1
                arg_name = nodes[i].value
                args.append(RIALVariable(arg_name, arg_type))
                i += 1
            else:
                break

        # Map RIAL args to llvm arg types
        llvm_args = [arg.llvm_type_as_function_arg for arg in args if not arg.name.endswith("...")]

        full_function_name = mangle_function_name(name, llvm_args, this_arg)
        full_function_name = f"{ParserState.module().name}:{full_function_name}"

        # Hasn't been declared previously, redeclare the function type here
        llvm_return_type = ParserState.map_type_to_llvm(return_type)
        func_type = self.llvmgen.create_function_type(llvm_return_type, llvm_args, False)

        # Create the actual function in IR
        func = self.llvmgen.create_function_with_type(full_function_name, name, func_type, linkage,
                                                      calling_convention,
                                                      FunctionDefinition(return_type, access_modifier, args,
                                                                         self.llvmgen.current_struct is not None and self.llvmgen.current_struct.name or "",
                                                                         unsafe))

        # Update the backing values
        for i in range(len(func.args)):
            func.definition.rial_args[i].backing_value = func.args[i]

        if not has_body:
            raise Discard()

        metadata_token = MetadataToken('Meta', full_function_name)
        metadata_token.metadata["func"] = func
        metadata_token.metadata["body_start"] = i
        nodes.pop(0)
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

        args: List[RIALVariable] = list()

        # Add class as implicit self parameter
        if self.llvmgen.current_struct is not None:
            args.append(RIALVariable("this", self.llvmgen.current_struct.name))

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
                args.append(RIALVariable(arg_name, arg_type))
                i += 1
            else:
                break

        # Map RIAL args to llvm arg types
        llvm_args = [arg.llvm_type_as_function_arg for arg in args if not arg.name.endswith("...")]

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

        # Create func type
        llvm_return_type = ParserState.map_type_to_llvm(return_type)
        func_type = self.llvmgen.create_function_type(llvm_return_type, llvm_args, False)

        # Create the actual function in IR
        func = self.llvmgen.create_function_with_type(full_function_name, name, func_type, linkage,
                                                      calling_convention,
                                                      FunctionDefinition(return_type, access_modifier, args,
                                                                         self.llvmgen.current_struct is not None and self.llvmgen.current_struct.name or "",
                                                                         unsafe))

        # Update the backing values
        for i in range(len(func.args)):
            func.definition.rial_args[i].backing_value = func.args[i]

        # Always inline the main function into the compiler supplied one
        if main_function:
            func.attributes.add('alwaysinline')

        # If it has no body we do not need to go through it later as it's already declared with this method.
        if not has_body:
            raise Discard()

        metadata_token = MetadataToken('Meta', full_function_name)
        metadata_token.metadata["func"] = func
        metadata_token.metadata["body_start"] = i
        nodes.pop(0)
        nodes.insert(0, metadata_token)

        return Tree('function_decl', nodes)
