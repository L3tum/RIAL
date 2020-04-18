import random
import string


def generate_random_name(count: int):
    return ''.join(random.choices(string.ascii_uppercase + string.ascii_lowercase + string.digits, k=count))


def rreplace(s, old, new, occurrence=-1):
    li = s.rsplit(old, occurrence)
    return new.join(li)
