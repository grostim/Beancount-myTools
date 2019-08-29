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
import datetime
from dateutil.parser import parse as parse_datetime
from importers.myutils import pdf_to_text
from beancount.core import amount, data, flags
from beancount.ingest import importer
from beancount.core.number import Decimal

class pdfbourso(importer.ImporterProtocol):
    """An importer for Boursorama PDF statements."""

    def __init__(self, accountList,
                 debug: bool = False,
               ):
        assert isinstance(accountList, dict), "La liste de comptes doit etre un type dict"
        self.accountList = accountList
        self.debug = debug

    def identify(self, file):
        if file.mimetype() != 'application/pdf':
            return False

        # Look for some words in the PDF file to figure out if it's a statement
        # from ACME. The filename they provide (Statement.pdf) isn't useful.On considéère que c'est un relevé Boursorama si on trouve le mot "BOURSORAMA" dedans.
        text = file.convert(pdf_to_text)
        if text:
            if re.search('BOURSORAMA BANQUE', text) is not None:
                self.type="Compte"
                return 1
            if re.search('BOUSFRPPXXX', text) is not None:
                self.type="Compte"
                return 1
            if re.search('Relevé de Carte', text) is not None:
                self.type="CB"
                return 1

    def file_name(self, file):
        # Normalize the name to something meaningful.
        return 'Boursorama.pdf'

    def file_account(self, file):
        #Recherche du numéro de compte dans le fichier.
        text = file.convert(pdf_to_text)
        if self.type == "Compte":
            control='8026\d\s*\d{11}'
        elif self.type == "CB":
            control='\s*4979\*{8}\d{4}'
        match = re.search(control, text)
        if match:
            compte = match.group(0).split(' ')[-1]
            control='8026\d\s*\d{11}'
            return self.accountList[compte]

    def file_date(self, file):
        # Get the actual statement's date from the contents of the file.
        text = file.convert(pdf_to_text)
        match = re.search('au\s*(\d*/\d*/\d*)', text)
        if match:
            return parse_datetime(match.group(1)).date()

    def extract(self, file, existing_entries=None):

        #Nom du fichier tel qu'il sera renommé.
        document = str(self.file_date(file)) + " " + self.file_name(file)

        # Open the pdf file and convert it to text
        entries = []
        text = file.convert(pdf_to_text)

        # Si debogage, affichage de l'extraction  
        if self.debug:
            print(text)

        if self.type == "Compte":
            #Identification du numéro de compte
            control='8026\d\s*\d{11}'
            match = re.search(control, text)
            if match:
                compte = match.group(0).split(' ')[-1]

            # Si debogage, affichage de l'extraction
            if self.debug:
                print(compte)

            control = 'SOLDE\s(?:EN\sEUR\s)?AU\s:(\s+)(\d{1,2}\/\d{2}\/\d{4})(\s+)((?:\d{1,3}\.)?\d{1,3},\d{2})'
            match = re.search(control, text)
            if match:
                datebalance = parse_datetime(match.group(2),dayfirst="True").date() + datetime.timedelta(1)
                longueur = len(match.group(1))+len(match.group(3))
                balance = match.group(4).replace(".", '').replace(",", '.')
            if longueur <77:
                #Si la distance entre les 2 champs est petite, alors, c'est un débit.
                balance = "-" + balance

            # Si debogage, affichage de l'extraction
            if self.debug:
                print(datebalance)
                print(balance)
                print(longueur)

            meta = data.new_metadata(file.name, 0)
            meta["source"] = "pdfbourso"
            meta["document"] = document

            entries.append(
                data.Balance(meta, datebalance,
                             self.accountList[compte], amount.Amount(Decimal(balance), "EUR"),
                             None, None))

            control='\d{1,2}\/\d{2}\/\d{4}\s(.*)\s(\d{1,2}\/\d{2}\/\d{4})\s(\s*)\s((?:\d{1,3}\.)?\d{1,3},\d{2})(?:(?:\n.\s{8,20})(.+?))?\n' #regexr.com/4ju06
            chunks = re.findall(control, text)

            # Si debogage, affichage de l'extraction
            if self.debug:
                print(chunks)

            index = 0
            for chunk in chunks:
                index += 1
                meta = data.new_metadata(file.name, index)
                meta["source"] = "pdfbourso"
                meta["document"] = document
                ope = dict()

                # Si debogage, affichage de l'extraction
                if self.debug:
                    print(chunk)

                ope["date"] = chunk[1]
                # Si debogage, affichage de l'extraction
                if self.debug:
                    print(ope["date"])

                ope["montant"] = chunk[3].replace(".", '').replace(",", '.')
                # Si debogage, affichage de l'extraction
                if self.debug:
                    print(ope["montant"])

                #Longueur de l'espace intercalaire
                longueur = len(chunk[0]) + len(chunk[2])
                # Si debogage, affichage de l'extraction
                if self.debug:
                    print(longueur)

                if longueur > 136:
                    ope["type"] = "Credit"
                else:
                    ope["type"] = "Debit"
                    ope["montant"] = "-" + ope["montant"]
                # Si debogage, affichage de l'extraction
                if self.debug:
                    print(ope["montant"])

                ope["payee"] = re.sub("\s+"," ",chunk[0])
                # Si debogage, affichage de l'extraction
                if self.debug:
                    print(ope["payee"])

                ope["narration"] = re.sub("\s+"," ",chunk[4])
                # Si debogage, affichage de l'extraction
                if self.debug:
                    print(ope["narration"])

                #Creation de la transaction
                posting_1 = data.Posting(
                    account=self.accountList[compte],
                    units=amount.Amount(Decimal(ope["montant"]), "EUR"),
                    cost=None,
                    flag=None,
                    meta=None,
                    price=None,
                )
                flag = flags.FLAG_OKAY
                transac = data.Transaction(
                    meta=meta,
                    date=parse_datetime(ope["date"],dayfirst="True").date(),
                    flag=flag,
                    payee=ope["payee"] or "inconnu",
                    narration=ope["narration"],
                    tags=data.EMPTY_SET,
                    links=data.EMPTY_SET,
                    postings=[posting_1],
                )
                entries.append(transac)
        return entries
