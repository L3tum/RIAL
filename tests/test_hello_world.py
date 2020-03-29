import os
import shutil
import sys
import unittest

from unittest.mock import patch

from rial.main import parse_arguments, main


class TestHelloWorld(unittest.TestCase):
    dir_path: str
    src_path: str
    main_file: str

    @classmethod
    def setUpClass(cls) -> None:
        super(cls, TestHelloWorld).setUpClass()
        cls.dir_path = os.path.join(os.path.abspath("/".join(f"{__file__}".split('/')[0:-1])), "TestHelloWorld")
        cls.src_path = os.path.join(cls.dir_path, "src")
        cls.main_file = os.path.join(cls.src_path, "main.rial")

        if not os.path.exists(cls.dir_path):
            os.mkdir(cls.dir_path)
            os.mkdir(cls.src_path)

        with open(cls.main_file, "w") as file:
            file.write("external void printf(CString format, params CString args);\n")
            file.write("void main() {\n")
            file.write('\tprintf("Hello World!");\n')
            file.write("}\n")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.dir_path)

    def test_correct_ir(self):
        testargs = ['prog', '--workdir', self.dir_path, '--opt-level', '3', '--print-ir', '--release']
        with patch.object(sys, 'argv', testargs):
            opts = parse_arguments()
            main(opts)

        with open(os.path.join(os.path.join(self.dir_path, "cache"), "main.ll"), "r") as ir:
            content = ir.read()

        self.assertIn('call void (i8*, ...) @"printf"', content)
        bin_size = os.path.getsize(os.path.join(os.path.join(self.dir_path, "bin"), "TestHelloWorld"))
        self.assertLessEqual(bin_size, 6016)


if __name__ == '__main__':
    unittest.main()
