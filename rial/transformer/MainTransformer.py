from llvmlite import ir
from llvmlite.ir import VoidType

from rial.concept.parser import Tree
from rial.concept.type_casting import get_casting_function
from rial.ir.RIALFunction import RIALFunction
from rial.ir.RIALIdentifiedStructType import RIALIdentifiedStructType
from rial.ir.RIALVariable import RIALVariable
from rial.ir.metadata.metadata_token import MetadataToken
from rial.transformer.BaseTransformer import BaseTransformer
from rial.transformer.builtin_type_to_llvm_mapper import Int32, is_builtin_type, map_llvm_to_type, map_shortcut_to_type
from rial.util.only_allowed_in_unsafe import only_allowed_in_unsafe


class MainTransformer(BaseTransformer):
    def start(self, tree: Tree):
        for node in tree.children:
            self.transform_helper(node)

    def array_assignment(self, tree: Tree):
        nodes = tree.children
        entry: RIALVariable = self.transform_helper(nodes[0])
        val: RIALVariable = self.transform_helper(nodes[2])

        assert isinstance(entry, RIALVariable)
        assert isinstance(val, RIALVariable)

        if entry.rial_type != val.rial_type:
            raise TypeError(entry, val)

        value = val.get_loaded_if_variable(self.module)

        self.module.builder.store(value, entry.value)

        return val

    def array_access(self, tree: Tree):
        nodes = tree.children
        variable: RIALVariable = self.transform_helper(nodes[0])
        index: RIALVariable = self.transform_helper(nodes[1])

        if isinstance(variable, ir.Type):
            ty: ir.Type = variable
            number = index
            assert isinstance(number, RIALVariable)

            name = map_llvm_to_type(ty)

            if isinstance(number.value, ir.Constant):
                number = number.value.constant
                arr_type = ir.ArrayType(ty, number)
                allocated = self.module.builder.alloca(arr_type)
                name = f"{name}[{number}]"
            elif number.is_variable:
                number = self.module.builder.load(number.value)
                arr_type = ty.as_pointer()
                allocated = self.module.builder.alloca(ty, number)
                # allocated = self.module.builder.gep(allocated, [Int32(0)])
                name = f"{name}[]"
            else:
                number = number.value
                arr_type = ty.as_pointer()
                allocated = self.module.builder.alloca(ty, number)
                # allocated = self.module.builder.gep(allocated, [Int32(0)])
                name = f"{name}[]"

            return RIALVariable(f"array_{name}", name, arr_type, allocated)

        if not variable.rial_type.endswith("]"):
            raise TypeError(variable)

        # Check if it's a "GEP array" as we only need one index then
        if isinstance(variable.value, ir.GEPInstr) or variable.rial_type.endswith("[]"):
            indices = [index.get_loaded_if_variable(self.module)]
        else:
            indices = [Int32(0), index.get_loaded_if_variable(self.module)]

        var = self.module.builder.gep(variable.value, indices)

        return RIALVariable(f"{variable.name}[{index}]", variable.array_element_type,
                            isinstance(variable.llvm_type,
                                       ir.ArrayType) and variable.llvm_type.element or variable.llvm_type.pointee,
                            var)

    def variable_assignment(self, tree: Tree):
        nodes = tree.children
        variable: RIALVariable = self.transform_helper(nodes[0])

        assert isinstance(variable, RIALVariable)

        value = self.transform_helper(nodes[2])

        if isinstance(value, RIALFunction):
            if value.function_type != variable.llvm_type:
                raise TypeError(value, variable)
            self.module.builder.store(self.module.builder.load(value), variable.value)
            return variable
        elif isinstance(value, RIALVariable):
            if value.rial_type != variable.rial_type:
                raise TypeError(value, variable)

            if variable.value.type.pointee == value.value.type:
                self.module.builder.store(value.value, variable.value)
            else:
                self.module.builder.store(value.get_loaded_if_variable(self.module), variable.value)
            return variable

        raise TypeError(value)

    def global_variable_assignment(self, tree: Tree):
        nodes = tree.children[0].children
        with self.module.create_in_global_ctor():
            variable: RIALVariable = self.transform_helper(nodes[0])

            assert isinstance(variable, RIALVariable)

            value = self.transform_helper(nodes[2])

            if isinstance(value, RIALFunction):
                if value.function_type != variable.llvm_type:
                    raise TypeError(value, variable)
                self.module.builder.store(self.module.builder.load(value), variable.value)
                return variable
            elif isinstance(value, RIALVariable):
                if value.rial_type != variable.rial_type:
                    raise TypeError(value, variable)

                self.module.builder.store(value.get_loaded_if_variable(self.module), variable.value)
                return variable

        raise TypeError(value)

    def variable_decl(self, tree: Tree):
        nodes = tree.children
        identifier = nodes[0].value
        value = self.transform_helper(nodes[2])

        if isinstance(value, RIALFunction):
            variable = self.module.builder.alloca(value.function_type)
            self.module.builder.store(self.module.builder.load(value), variable)
            variable = RIALVariable(identifier, str(value.function_type).replace("i8*", "Char[]"), value.function_type,
                                    variable)
        elif isinstance(value, RIALVariable):
            if value.is_variable:
                variable = value
            else:
                variable = self.module.builder.alloca(value.llvm_type)
                self.module.builder.store(value.get_loaded_if_variable(self.module), variable)
                variable = RIALVariable(identifier, value.rial_type, value.llvm_type, variable)
        else:
            raise TypeError(value, nodes)

        self.module.current_block.add_named_value(identifier, variable)

        return variable

    def cast(self, tree: Tree):
        nodes = tree.children
        ty = self.module.get_definition(nodes[0])
        value: RIALVariable = self.transform_helper(nodes[1])

        if isinstance(ty, ir.Type) and is_builtin_type(map_llvm_to_type(ty)):
            # Simple cast for primitive to primitive
            if is_builtin_type(value.rial_type):
                cast_function = get_casting_function(value.llvm_type, ty)

                if hasattr(self.module.builder, cast_function):
                    casted = getattr(self.module.builder, cast_function)(value.get_loaded_if_variable(self.module), ty)
                    return RIALVariable("cast", map_llvm_to_type(ty), ty, casted)
                else:
                    raise TypeError(f"No casting function found for casting {value.rial_type} to {nodes[0]}")
            else:
                # Casting type to integer ("pointer") (unsafe!)
                with only_allowed_in_unsafe():
                    casted = self.module.builder.ptrtoint(value.value, ty)
                    return RIALVariable("cast", map_llvm_to_type(ty), ty, casted)
        elif isinstance(ty, RIALIdentifiedStructType):
            # Casting integer to type (unsafe!)
            if is_builtin_type(value.rial_type):
                with only_allowed_in_unsafe():
                    casted = self.module.builder.inttoptr(value.get_loaded_if_variable(self.module), ty.as_pointer())
                    return RIALVariable("cast", ty.name, ty, casted)
            else:
                # Simple type cast
                casted = self.module.builder.bitcast(value.value, ty.as_pointer())
                return RIALVariable("cast", ty.name, ty, casted)

        raise TypeError(ty, value)

    def struct_decl(self, tree: Tree):
        nodes = tree.children
        node = nodes[0]
        struct = node.metadata['struct']
        function_decls = node.metadata['functions']

        if struct is None:
            raise KeyError("Expected a struct but couldn't find it!")

        self.module.current_struct = struct

        # Create functions
        for func_decl in function_decls:
            self.transform_helper(func_decl)

        self.module.current_struct = None

    def function_decl(self, tree: Tree):
        nodes = tree.children

        node: MetadataToken = nodes[0]
        assert isinstance(node, MetadataToken)
        body_start = node.metadata['body_start']
        func: RIALFunction = node.metadata['func']

        if func is None:
            raise KeyError("Expected a function but didn't find it!")

        with self.module.create_or_enter_function_body(func):
            for node in nodes[body_start:]:
                self.transform_helper(node)

    def return_rule(self, tree: Tree):
        nodes = tree.children

        if self.module.current_block.terminator is not None:
            raise PermissionError("Return after return")

        if len(nodes) == 0:
            self.module.builder.ret_void()
            return

        variable: RIALVariable = self.transform_helper(nodes[0])

        assert isinstance(variable, RIALVariable)

        if variable.rial_type != self.module.current_func.definition.rial_return_type:
            raise TypeError(variable.rial_type, self.module.current_func.definition.rial_return_type)

        if isinstance(variable.llvm_type, VoidType):
            self.module.builder.ret_void()
        elif is_builtin_type(variable.rial_type):
            self.module.builder.ret(variable.get_loaded_if_variable(self.module))
        # Special case for CStrings for now
        elif self.module.current_func.definition.rial_return_type == map_shortcut_to_type("CString") and isinstance(
                variable.value.type.pointee, ir.PointerType):
            self.module.builder.ret(self.module.builder.load(variable.value))
        else:
            self.module.builder.ret(variable.value)
