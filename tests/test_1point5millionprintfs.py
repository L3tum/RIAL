import os
import shutil
import sys
import unittest

from unittest.mock import patch

import pytest

from rial.main import parse_arguments, main


class Test1Point5MillionPrintfs(unittest.TestCase):
    dir_path: str
    src_path: str
    main_file: str

    @classmethod
    def setUpClass(cls) -> None:
        super(cls, Test1Point5MillionPrintfs).setUpClass()
        cls.dir_path = os.path.join(os.path.abspath("/".join(f"{__file__}".split('/')[0:-1])), "1point5millionprintfs")
        cls.src_path = os.path.join(cls.dir_path, "src")
        cls.main_file = os.path.join(cls.src_path, "main.rial")

        if not os.path.exists(cls.dir_path):
            os.mkdir(cls.dir_path)
            os.mkdir(cls.src_path)

        with open(cls.main_file, "w") as file:
            file.write("external void printf(CString format, params CString args);\n")
            file.write("void main() {\n")

            for i in range(1_500_000):
                file.write('\tprintf("%i \\n\\0", 5 + 5);\n')

            file.write("}\n")

    @pytest.fixture(autouse=True)
    def setupBenchmark(self, benchmark):
        self.benchmark = benchmark

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.dir_path)

    @pytest.mark.benchmark(
        max_time=130,
        min_rounds=1
    )
    def test_compile_speed_no_opt(self):
        testargs = ['prog', '--workdir', self.dir_path, '--opt-level', 0]
        with patch.object(sys, 'argv', testargs):
            opts = parse_arguments()
            # self.benchmark(main, opts)


if __name__ == '__main__':
    unittest.main()
