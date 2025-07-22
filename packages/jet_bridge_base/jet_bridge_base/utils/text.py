import re


def clean_alphanumeric(str):
    return _alphanum_pattern.sub('-', str)

_alphanum_pattern = re.compile('[^0-9a-zA-Z.]+')
