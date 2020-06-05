from typing import Optional

from rial.concept.parser import Tree, Discard, Token
from rial.ir.RIALVariable import RIALVariable
from rial.transformer.BaseTransformer import BaseTransformer


class LoopTransformer(BaseTransformer):
    def continue_rule(self, tree: Tree):
        if self.module.conditional_block is None:
            raise PermissionError("Continue outside of loop")

        self.module.builder.branch(self.module.conditional_block.block)

        raise Discard()

    def break_rule(self, tree: Tree):
        if self.module.end_block is None:
            raise PermissionError("Break outside of loop")

        self.module.builder.branch(self.module.end_block.block)

        raise Discard()

    def loop_loop(self, tree: Tree):
        nodes = tree.children
        name = self.module.current_block.block.name
        body_block = self.module.builder.create_block(f"{name}.loop.body", parent=self.module.current_block)
        end_block = self.module.builder.create_block(f"{name}.loop.end", sibling=self.module.current_block)

        old_conditional_block = self.module.conditional_block
        old_end_block = self.module.end_block
        self.module.builder.create_jump(body_block)
        self.module.builder.enter_block(body_block)
        self.module.conditional_block = body_block
        self.module.end_block = end_block

        # Build body
        for node in nodes:
            self.transform_helper(node)

        # Jump back into body
        if not self.module.current_block.block.is_terminated:
            self.module.builder.create_jump(body_block)

        # Go out of loop
        self.module.builder.enter_block(end_block)
        self.module.conditional_block = old_conditional_block
        self.module.end_block = old_end_block

    def for_loop(self, tree: Tree):
        nodes = tree.children
        name = self.module.current_block.block.name
        name = f"{name}.for.wrapper"

        wrapper_block = self.module.builder.create_block(name, parent=self.module.current_block)
        conditional_block = self.module.builder.create_block(f"{name}.condition", parent=wrapper_block)
        body_block = self.module.builder.create_block(f"{name}.body", sibling=wrapper_block)
        end_block = self.module.builder.create_block(f"{name}.end", sibling=self.module.current_block)
        old_conditional_block = self.module.conditional_block
        old_end_block = self.module.end_block

        self.module.builder.create_jump(wrapper_block)
        self.module.builder.enter_block(wrapper_block)
        self.module.conditional_block = wrapper_block
        self.module.end_block = end_block

        # Create variable in wrapper block
        self.transform_helper(nodes[0])

        self.module.builder.create_jump(conditional_block)
        self.module.builder.enter_block(conditional_block)
        self.module.conditional_block = conditional_block

        # Create condition
        condition: RIALVariable = self.transform_helper(nodes[1])
        assert isinstance(condition, RIALVariable)
        self.module.builder.create_conditional_jump(condition.get_loaded_if_variable(self.module), body_block,
                                                    end_block)

        # Go into body
        self.module.builder.enter_block(body_block)

        # Build body
        for node in nodes[3:]:
            self.transform_helper(node)

        # Build incrementor
        if not self.module.current_block.block.is_terminated:
            self.transform_helper(nodes[2])

        # Create jump back into condition
        if not self.module.current_block.block.is_terminated:
            self.module.builder.create_jump(conditional_block)

        # Get out of loop
        self.module.builder.enter_block(end_block)
        self.module.conditional_block = old_conditional_block
        self.module.end_block = old_end_block

    def while_loop(self, tree: Tree):
        nodes = tree.children
        name = f"{self.module.current_block.block.name}.while"
        conditional_block = self.module.builder.create_block(f"{name}.condition", parent=self.module.current_block)
        body_block = self.module.builder.create_block(f"{name}.body", parent=conditional_block)
        end_block = self.module.builder.create_block(f"{name}.end", sibling=self.module.current_block)
        old_conditional_block = self.module.conditional_block
        old_end_block = self.module.end_block

        self.module.builder.create_jump(conditional_block)
        self.module.builder.enter_block(conditional_block)
        self.module.conditional_block = conditional_block
        self.module.end_block = end_block

        # Build condition
        condition: RIALVariable = self.transform_helper(nodes[0])
        assert isinstance(condition, RIALVariable)
        self.module.builder.create_conditional_jump(condition.get_loaded_if_variable(self.module), body_block,
                                                    end_block)

        # Go into body
        self.module.builder.enter_block(body_block)

        # Build body
        for node in nodes[1:]:
            self.transform_helper(node)

        # Jump back into condition
        if not self.module.current_block.block.is_terminated:
            self.module.builder.create_jump(conditional_block)

        # Get out of loop
        self.module.builder.enter_block(end_block)
        self.module.conditional_block = old_conditional_block
        self.module.end_block = old_end_block

    def conditional_block(self, tree: Tree):
        nodes = tree.children
        name = f"{self.module.current_block.block.name}.conditional"
        condition = nodes[0]
        likely_unlikely_modifier: Token = nodes[1]
        body = nodes[2]
        else_conditional: Optional[Tree] = len(nodes) > 3 and nodes[3] or None
        else_likely_unlikely_modifier = Token('STANDARD_WEIGHT', 50)

        if else_conditional is not None:
            if else_conditional.data == "conditional_else_block":
                else_likely_unlikely_modifier = else_conditional.children[0]
                else_conditional.children.pop(0)
            else:
                # Else-If
                # If the IF Condition is likely, then the else if is automatically unlikely
                # If the IF Condition is unlikely, then the else if is automatically likely
                # This is done because the last ELSE is the opposite of the first IF and thus the ELSE IFs are automatically gone through to get there.
                # The original ELSE IF weight is used in the following conditional blocks (that were inserted in this generated ELSE block).
                if likely_unlikely_modifier.type == "LIKELY":
                    else_likely_unlikely_modifier = Token("UNLIKELY", 10)
                else:
                    else_likely_unlikely_modifier = Token("LIKELY", 100)

        else_block = None

        conditional_block = self.module.builder.create_block(f"{name}.condition", parent=self.module.current_block)
        body_block = self.module.builder.create_block(f"{name}.body", parent=conditional_block)
        end_block = self.module.builder.create_block(f"{name}.end", sibling=self.module.current_block)
        old_conditional_block = self.module.conditional_block
        old_end_block = self.module.end_block

        if else_conditional is not None:
            else_block = self.module.builder.create_block(f"{name}.else", parent=conditional_block)

        if likely_unlikely_modifier.type == else_likely_unlikely_modifier.type and likely_unlikely_modifier.type != "STANDARD_WEIGHT":
            # log_warn(
            #     f"{ParserState.module().filename}[{likely_unlikely_modifier.line}:{likely_unlikely_modifier.column}]WARNING 002")
            # log_warn(f"Specifying the same weight on both conditionals cancels them out.")
            # log_warn(f"Both can be safely removed.")
            pass

        # Create condition
        self.module.builder.create_jump(conditional_block)
        self.module.builder.enter_block(conditional_block)
        cond: RIALVariable = self.transform_helper(condition)
        assert isinstance(cond, RIALVariable)
        self.module.builder.create_conditional_jump(cond.get_loaded_if_variable(self.module), body_block,
                                                    else_block is not None and else_block or end_block,
                                                    [likely_unlikely_modifier.value,
                                                     else_likely_unlikely_modifier.value])

        # Create body
        self.module.builder.enter_block(body_block)
        for node in body.children:
            self.transform_helper(node)

        # Jump out of body
        if not self.module.current_block.block.is_terminated:
            self.module.builder.create_jump(end_block)

        # Create else if necessary
        if len(nodes) > 3:
            self.module.builder.enter_block(else_block)
            for node in else_conditional.children:
                self.transform_helper(node)
            if not self.module.current_block.block.is_terminated:
                self.module.builder.create_jump(end_block)

        # Leave conditional block
        self.module.builder.enter_block(end_block)
        self.module.conditional_block = old_conditional_block
        self.module.end_block = old_end_block

    def shorthand_if(self, tree: Tree):
        nodes = tree.children
        name = f"{self.module.current_block.block.name}.shorthand_conditional"
        conditional_block = self.module.builder.create_block(f"{name}.condition", parent=self.module.current_block)
        body_block = self.module.builder.create_block(f"{name}.body", parent=conditional_block)
        else_block = self.module.builder.create_block(f"{name}.else", parent=conditional_block)
        end_block = self.module.builder.create_block(f"{name}.end", sibling=self.module.current_block)
        old_conditional_block = self.module.conditional_block
        old_end_block = self.module.end_block

        # Create condition
        self.module.builder.create_jump(conditional_block)
        self.module.builder.enter_block(conditional_block)
        cond: RIALVariable = self.transform_helper(nodes[0])
        assert isinstance(cond, RIALVariable)
        self.module.builder.create_conditional_jump(cond.get_loaded_if_variable(self.module), body_block, else_block)

        # Create body
        self.module.builder.enter_block(body_block)
        true_value: RIALVariable = self.transform_helper(nodes[1])
        assert isinstance(true_value, RIALVariable)

        # Jump out of body
        if not self.module.current_block.block.is_terminated:
            self.module.builder.create_jump(end_block)

        # Create else
        self.module.builder.enter_block(else_block)
        false_value: RIALVariable = self.transform_helper(nodes[2])
        assert isinstance(false_value, RIALVariable)

        # Jump out of else
        if not self.module.current_block.block.is_terminated:
            self.module.builder.create_jump(end_block)

        # Leave conditional block
        self.module.builder.enter_block(end_block)

        # PHI the values
        phi = self.module.builder.phi(true_value.llvm_type)
        phi.add_incoming(true_value.value, body_block.block)
        phi.add_incoming(false_value.value, else_block.block)
        self.module.conditional_block = old_conditional_block
        self.module.end_block = old_end_block

        return RIALVariable("phi", true_value.rial_type, true_value.llvm_type, phi)

    def switch_block(self, tree: Tree):
        nodes = tree.children
        parent = self.module.current_block
        variable: RIALVariable = self.transform_helper(nodes[0])
        assert isinstance(variable, RIALVariable)
        end_block = self.module.builder.create_block(f"{self.llvmgen.current_block.block.name}.end_switch",
                                                     sibling=self.llvmgen.current_block)
        old_end_block = self.module.end_block
        old_conditional_block = self.module.conditional_block
        self.module.end_block = end_block
        self.module.conditional_block = None
        switch = self.module.builder.switch(variable.get_loaded_if_variable(self.module), None)
        collected_empties = list()

        for node in nodes[1:]:
            var, block = self.transform_helper(node)

            # Check if just case, collect for future use
            if block is None:
                collected_empties.append(var)
            else:
                self.module.builder.enter_block_end(block)

                # Check if default case and set as default
                if var is None:
                    if switch.default is not None:
                        raise PermissionError(f"{self.module.name} Duplicate default case in switch statement")
                    else:
                        switch.default = block.block
                else:
                    switch.add_case(var, block.block)

                # Add all collected cases
                for collected_empty in collected_empties:
                    switch.add_case(collected_empty, block.block)

                collected_empties.clear()

            self.module.builder.enter_block_end(parent)

        if switch.default is None:
            switch.default = end_block.block

        if len(collected_empties) > 0:
            raise PermissionError("Empty cases in switch statement!")

        self.module.end_block = old_end_block
        self.module.conditional_block = old_conditional_block
        self.module.builder.enter_block(end_block)

    def switch_case(self, tree: Tree):
        nodes = tree.children
        var: RIALVariable = self.transform_helper(nodes[0])
        assert isinstance(var, RIALVariable)

        # We need to load here as we are still in the parent's block and not the conditional block
        var = var.get_loaded_if_variable(self.module)

        if len(nodes) == 1:
            return var, None
        block = self.module.builder.create_block(f"{self.module.current_block.block.name}.switch.case",
                                                 self.module.current_block)
        self.module.builder.enter_block(block)

        for node in nodes[1:]:
            self.transform_helper(node)

        if not self.module.current_block.block.is_terminated:
            self.module.builder.ret_void()

        self.module.current_block = self.module.current_block.parent

        return var, block

    def default_case(self, tree: Tree):
        nodes = tree.children
        block = self.module.builder.create_block(f"{self.module.current_block.block.name}.switch.default",
                                                 self.module.current_block)
        self.module.builder.enter_block(block)
        for node in nodes:
            self.transform_helper(node)

        if not self.module.current_block.block.is_terminated:
            self.module.builder.ret_void()

        self.module.current_block = self.module.current_block.parent

        return None, block
