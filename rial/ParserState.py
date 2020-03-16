from typing import Dict


class ParserState(object):
    global_variables: Dict

    def __init__(self):
        self.global_variables = dict()
