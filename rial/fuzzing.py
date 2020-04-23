import shutil
from pathlib import Path
from random import random

from munch import munchify
from pythonfuzz.main import PythonFuzz

from rial.main import main, DEFAULT_OPTIONS


@PythonFuzz
def fuzz(buf):
    string = buf.decode("unicode")
    cur_directory = Path(__file__.replace("fuzzing.py", ""))
    tmp_directory = cur_directory.joinpath(f"tmp_{random()}")
    tmp_directory.mkdir(parents=False, exist_ok=False)
    src_directory = tmp_directory.joinpath("src")
    src_directory.mkdir(parents=False, exist_ok=False)

    with open(src_directory.joinpath("main.rial"), "w") as file:
        file.write(string)

    ops = DEFAULT_OPTIONS['config']
    ops['workdir'] = str(tmp_directory)

    if random() % 2 == 0:
        ops['release'] = True
        ops['opt_level'] = "3"
        ops['strip'] = True

    try:
        main(munchify(ops))
    except:
        raise
    finally:
        shutil.rmtree(tmp_directory)


if __name__ == '__main__':
    fuzz()
