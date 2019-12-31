"""Importer pour fiche de payes personnelle. (Format propre à mon employeur)
Classement des fichiers uniquement. Pas d'import des transactions.
"""
__copyright__ = "Copyright (C) 2016  Martin Blais / Mofified in 2019 by Grostim"
__license__ = "GNU GPLv2"


import re
import datetime
from dateutil.parser import parse as parse_datetime
from myTools.myutils import pdf_to_text
from beancount.core import amount, data, flags
from beancount.ingest import importer
from beancount.core.number import Decimal, D


class fichepaye(importer.ImporterProtocol):
    """An importer for my own pay slip."""

    def __init__(self, accountList, debug: bool = False):
        assert isinstance(
            accountList, dict
        ), "La liste de comptes doit etre un type dict"
        self.accountList = accountList
        self.debug = debug

    def identify(self, file):
        if file.mimetype() != "application/pdf":
            return False

        # On considére que c'est une feuille de paye de mon employeur si on trouve cet identifiant.
        text = file.convert(pdf_to_text)
        # Si debogage, affichage de l'extraction
        if self.debug:
            print(text)
        if text:
            if re.search("Sage", text) is not None:
                return 1

    def file_account(self, file):
        # Recherche du numéro de compte dans le fichier.
        text = file.convert(pdf_to_text)
        control = "025680471 00015"
        match = re.search(control, text)
        # Si debogage, affichage de l'extraction
        if self.debug:
            print(match.group(0))
        if match:
            compte = match.group(0)
            return self.accountList[compte]

    def file_name(self, file):
        # Normalize the name to something meaningful.
        # Recherche du numéro de compte dans le fichier.
        return "Bulletin_Paye.pdf"

    def file_date(self, file):
        # Get the actual statement's date from the contents of the file.
        text = file.convert(pdf_to_text)
        control = "Paiement\sle\s*(\d{2}\/\d{2}\/\d{2})"
        match = re.search(control, text)
        if match:
            return parse_datetime(match.group(1), dayfirst="True").date()

    def extract(self, file, existing_entries=None):
        # Nom du fichier tel qu'il sera renommé.
        document = str(self.file_date(file)) + " " + self.file_name(file)


        # Open the pdf file and create directives.
        entries = []
        text = file.convert(pdf_to_text)

        # Si debogage, affichage de l'extraction  
        if self.debug:
            print(text)

        control = "025680471 00015"
        match = re.search(control, text)
        # Si debogage, affichage de l'extraction
        if self.debug:
            print(match.group(0))
        if match:
            compte = match.group(0)

        # On relève le net à payer avant IR
        control = 'Cadre Net à payer\n\s*(\d{1,4}\,\d{2})'
        match = re.search(control, text)
        netAvantIR = amount.Amount(-1 * Decimal(match.group(1).replace(",", '.').replace(" ", '')), "EUR")
        # Si debogage, affichage de l'extraction
        if self.debug:
            print(netAvantIR)

        posting_1 = data.Posting(
            account=self.accountList[compte] + ":Salaire",
            units=netAvantIR,
            cost=None,
            flag=None,
            meta=None,
            price=None,
        )
        if self.debug:
            print(posting_1)

        # On relève le montant IR
        control = 'Impôt sur le revenu prélevé à la source.*\s(\d{1,4}\,\d{2})\n'
        match = re.search(control, text)
        IRsource = amount.Amount(1 * Decimal(match.group(1).replace(",", '.').replace(" ", '')), "EUR")
        # Si debogage, affichage de l'extraction
        if self.debug:
            print(IRsource)
        posting_2 = data.Posting(
            account="Depenses:Impots:IR",
            units=IRsource,
            cost=None,
            flag=None,
            meta=None,
            price=None,
        )
        if self.debug:
            print(posting_2)

        # On relève le Net à Payer
        control = 'NetAPayer.*\s(\d{1,4}\,\d{2})\n'
        match = re.search(control, text)
        netAPayer = amount.Amount(1* Decimal(match.group(1).replace(",", '.').replace(" ", '')), "EUR")
        # Si debogage, affichage de l'extraction
        if self.debug:
            print(netAPayer)
        posting_3 = data.Posting(
            account="Actif:Boursorama:CCTim",
            units=netAPayer,
            cost=None,
            flag=None,
            meta=None,
            price=None,
        )
        if self.debug:
            print(posting_3)

        flag = flags.FLAG_OKAY

        meta = data.new_metadata(file.name, 0)
        meta["source"] = "fichepaye"
        meta["document"] = document
        transac = data.Transaction(
            meta=meta,
            date=self.file_date(file),
            flag=flag,
            payee="VIR SEPA TECNAL S.A.S",
            narration="VIREMENT-SALAIRE",
            tags=data.EMPTY_SET,
            links=data.EMPTY_SET,
            postings=[posting_1,posting_2,posting_3],
            )
        entries.append(transac)



        return entries
