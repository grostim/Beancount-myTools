"""Importer for PDF statements from BinckBanck.
Classement des fichiers uniquement. Pas d'import des transactions.
"""
__copyright__ = (
    "Copyright (C) 2016  Martin Blais / Mofified in 2019 by Grostim"
)
__license__ = "GNU GPLv2"


import re
import datetime
from dateutil.parser import parse as parse_datetime
from myTools.myutils import pdf_to_text
from beancount.core import amount, data, flags
from beancount.ingest import importer
from beancount.core.number import Decimal, D


class pdfbinck(importer.ImporterProtocol):
    """An importer for Binck PDF statements."""

    def __init__(self, accountList, debug: bool = False):
        assert isinstance(
            accountList, dict
        ), "La liste de comptes doit etre un type dict"
        self.accountList = accountList
        self.debug = debug

    def identify(self, file):
        if file.mimetype() != "application/pdf":
            return False

        # On considére que c'est un relevé Boursorama si on trouve le début de l'IBAN Binck dedans.
        text = file.convert(pdf_to_text)
        # Si debogage, affichage de l'extraction
        if self.debug:
            print(text)
        if text:
            if re.search("FR76158", text) is not None:
                return 1

    def file_account(self, file):
        # Recherche du numéro de compte dans le fichier.
        text = file.convert(pdf_to_text)
        control = r"N° compte :\s*(\d{2}\.\d{2}\.\d{3})"
        match = re.search(control, text)
        # Si debogage, affichage de l'extraction
        if self.debug:
            print(match.group(1))
        if match:
            compte = match.group(1)
            return self.accountList[compte]

    def file_name(self, file):
        # Normalize the name to something meaningful.
        # Recherche du numéro de compte dans le fichier.
        text = file.convert(pdf_to_text)
        control = r"Opérations :\s*(\d*-\d*)"
        match = re.search(control, text)
        return "Ope " + match.group(1) + " Binck.pdf"

    def file_date(self, file):
        # Get the actual statement's date from the contents of the file.
        text = file.convert(pdf_to_text)
        control = r"Date:\s*(\d{2}-\d{2}-\d{4})"
        match = re.search(control, text)
        if match:
            return parse_datetime(match.group(1), dayfirst="True").date()
