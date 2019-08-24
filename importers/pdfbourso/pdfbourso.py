"""Importer for PDF statements from Boursorama.

This importer identifies the file from its contents and only supports filing, it
cannot extract any transactions from the PDF conersion to text. This is common,
and I figured I'd provide an example for how this works.

Furthermore, it uses an external library called pdftotext, which may or may not be installed on
your machine. This example shows how to write a test that gets skipped
automatically when an external tool isn't installed.
"""
__copyright__ = "Copyright (C) 2016  Martin Blais / Mofified in 2019 by Grostim"
__license__ = "GNU GPLv2"

import re
import subprocess

from dateutil.parser import parse as parse_datetime

from beancount.ingest import importer

def is_pdfminer_installed():
    """Return true if the external Pdftotxt tool installed."""
    try:
        returncode = subprocess.call(['pdftotext', '-v'],
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
    except (FileNotFoundError, PermissionError):
        return False
    else:
        return returncode == 0


def pdf_to_text(filename):
    """Convert a PDF file to a text equivalent.

    Args:
      filename: A string path, the filename to convert.
    Returns:
      A string, the text contents of the filename.
    """
    pipe = subprocess.Popen(['pdftotext', '-layout', filename, '-'],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    stdout, stderr = pipe.communicate()
    if stderr:
        raise ValueError(stderr.decode())
    return stdout.decode()


class pdfbourso(importer.ImporterProtocol):
    """An importer for Boursorama PDF statements."""

    def __init__(self, accountList):
        assert isinstance(accountList, dict), "La liste de comptes doit etre un type dict"
        self.accountList = accountList

    def identify(self, file):
        if file.mimetype() != 'application/pdf':
            return False

        # Look for some words in the PDF file to figure out if it's a statement
        # from ACME. The filename they provide (Statement.pdf) isn't useful.On considéère que c'est un relevé Boursorama si on trouve le mot "BOURSORAMA" dedans.
        text = file.convert(pdf_to_text)
        if text:
            return re.search('BOURSORAMA BANQUE', text) is not None

    def file_name(self, file):
        # Normalize the name to something meaningful.
        return 'Releve.pdf'

    def file_account(self, file):
        #Recherche du numéro de compte dans le fichier.
        text = file.convert(pdf_to_text)
        match = re.search('80261\s*\d{11}', text)
        if match:
            compte = match.group(0).split(' ')[-1]
            return self.accountList[compte]

    def file_date(self, file):
        # Get the actual statement's date from the contents of the file.
        text = file.convert(pdf_to_text)
        match = re.search('au\s*(\d*/\d*/\d*)', text)
        if match:
            return parse_datetime(match.group(1)).date()

