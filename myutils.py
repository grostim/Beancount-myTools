""" Diverses fonctions utiles communes à mes importers.
"""

__copyright__ = "Copyright (C) 2019 Grostim"
__license__ = "GNU GPLv2"

import subprocess


def is_pdfminer_installed():
    """
    It checks if the pdftotext command is available on the system.

    Args:
      None

    Returns:
      The returncode of the subprocess call.
    """

    try:
        returncode = subprocess.call(
            ["pdftotext", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except (FileNotFoundError, PermissionError):
        return False
    else:
        return returncode == 0


def pdf_to_text(filename):
    """
    It takes a PDF file and converts it to a text file.
    Args:
      filename: A string path, the filename to convert
    Returns:
      A string, the text contents of the filename.
    """
    pipe = subprocess.Popen(
        ["pdftotext", "-layout", filename, "-"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = pipe.communicate()
    if stderr:
        raise ValueError(stderr.decode())
    return stdout.decode()


def traduire_mois(str):
    """
    Traduction des abréviations de mois
    Args:
      str: the string to be translated
    Returns:
      The string "feb"
    """
    str = str.replace("fév", "feb")
    str = str.replace("mars", "mar")
    str = str.replace("avr", "apr")
    str = str.replace("mai", "may")
    str = str.replace("juin", "jun")
    str = str.replace("juil", "jul")
    str = str.replace("août", "aug")
    str = str.replace("déc", "dec")
    return str
