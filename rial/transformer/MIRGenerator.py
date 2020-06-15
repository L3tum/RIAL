from typing import Optional, List

from rial.concept.Transformer import Transformer
from rial.concept.parser import Token, Str
from rial.mir.Block import Block
from rial.mir.FunctionDefinition import FunctionDefinition
from rial.mir.GlobalDefinition import GlobalDefinition
from rial.mir.Module import Module
from rial.mir.SourceSpan import SourceSpan
from rial.mir.Value import Value
from rial.mir.builtin_types.Array import Array
from rial.mir.builtin_types.Boolean import Boolean
from rial.mir.builtin_types.Double import Double
from rial.mir.builtin_types.Float import Float
from rial.mir.builtin_types.Half import Half
from rial.mir.builtin_types.Integer import Integer
from rial.mir.builtin_types.Null import Null
from rial.util.util import good_hash


class MIRGenerator(Transformer):
    current_module: Optional[Module]
    current_function: Optional[FunctionDefinition]
    current_block: Optional[Block]

    def number(self, nodes: List[Token]):
        value: str = nodes[0].value
        value.replace("_", "")
        value_lowered = value.lower()
        source_span = SourceSpan.from_token(nodes[0])

        if "." in value or "e" in value:
            if value.endswith("f"):
                return Value(source_span, Float(), value=float(value.strip("f")))
            if value.endswith("h"):
                return Value(source_span, Half(), value=float(value.strip("h")))
            return Value(source_span, Double(), value=float(value.strip("d")))

        if value.startswith("0x"):
            return Value(source_span, Integer(), value=int(value, 16))

        if value.startswith("0b"):
            return Value(source_span, Integer(), value=int(value, 2))

        if value_lowered.endswith("ub"):
            return Value(source_span, Integer(unsigned=True, bit_width=8), value=int(value_lowered.strip("ub")))

        if value_lowered.endswith("b"):
            return Value(source_span, Integer(bit_width=8), value=int(value_lowered.strip("b")))

        if value_lowered.endswith("ul"):
            return Value(source_span, Integer(unsigned=True, bit_width=64), value=int(value_lowered.strip("ul")))

        if value_lowered.endswith("u"):
            return Value(source_span, Integer(unsigned=True), value=int(value_lowered.strip("u")))

        if value_lowered.endswith("l"):
            return Value(source_span, Integer(bit_width=64), value=int(value_lowered.strip("b")))

        return Value(source_span, Integer(), value=int(value))

    def true(self, nodes: List[Token]):
        return Value(SourceSpan.from_token(nodes[0]), Boolean(), value=True)

    def false(self, nodes: List[Token]):
        return Value(SourceSpan.from_token(nodes[0]), Boolean(), value=False)

    def null(self, nodes: List[Token]):
        return Value(SourceSpan.from_token(nodes[0]), Null(), value=None)

    def string(self, nodes: List[Token]):
        value = nodes[0].value.strip("\"")
        name = ".const.str.%s" % good_hash(value)

        existing = self.current_module.get_global_definition(name)
        if existing is not None:
            return existing

        # Parse escape codes to be correct
        value = eval("'{}'".format(value))
        source_span = SourceSpan.from_token(nodes[0])
        val = Value(source_span, Str(), value)
        glob = GlobalDefinition(source_span, name, val)

        self.current_module.globs.append(glob)

        return glob

    def cstring(self, nodes: List[Token]):
        value = nodes[0].value.strip("\"")
        name = ".const.cstr.%s" % good_hash(value)

        existing = self.current_module.get_global_definition(name)
        if existing is not None:
            return existing

        # Parse escape codes to be correct
        value = eval("'{}'".format(value))
        value = f"{value}\00"
        arr = bytearray(value.encode("utf-8"))
        source_span = SourceSpan.from_token(nodes[0])
        val = Value(source_span, Array(type=Integer(unsigned=True, bit_width=8), count=len(arr)), arr)
        glob = GlobalDefinition(source_span, name, val)

        self.current_module.globs.append(glob)

        return glob
