"""Importer for PDF statements from Boursorama.

This importer identifies the file from its contents and only supports filing, it
cannot extract any transactions from the PDF conersion to text. This is common,
and I figured I'd provide an example for how this works.

Furthermore, it uses an external library called pdftotext, which may or may not be installed on
your machine. This example shows how to write a test that gets skipped
automatically when an external tool isn't installed.
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


class pdfbourso(importer.ImporterProtocol):
    """An importer for Boursorama PDF statements."""

    def __init__(self, accountList, debug: bool = False):
        """
        This function is used to create an instance of the class.
        It takes a list of accounts as a parameter and returns an instance of the class.
        The class has two attributes: a list of accounts and a boolean debug flag.

        :param accountList: A dictionary of accounts
        :param debug: bool = False, defaults to False
        :type debug: bool (optional)
        :return: None
        """
        assert isinstance(
            accountList, dict
        ), "La liste de comptes doit etre un type dict"
        self.accountList = accountList
        self.debug = True

    def identify(self, file):
        """
        The identify function takes a file as an argument and returns a boolean value.
        If the file is a pdf, it converts it to text and checks if the text contains
        the words "Relevé de Carte" or "BOURSORAMA BANQUE". If it does, it returns True.
        Otherwise, it returns False.

        :param file: the file to be processed
        :return: The type of the file.
        """

        if file.mimetype() != "application/pdf":
            return False

        text = file.convert(pdf_to_text)
        if self.debug:
            print(text)
        if text:
            if re.search("Relevé de Carte", text) is not None:
                self.type = "CB"
                return 1
            if (
                re.search(
                    r"BOURSORAMA BANQUE|BOUSFRPPXXX|RCS\sNanterre\s351\s?058\s?151",
                    text,
                )
                is not None
            ):
                self.type = "Compte"
                return 1
            if (
                re.search(
                    r"tableau d'amortissement|Echéancier Prévisionnel|Échéancier Définitif",
                    text,
                )
                is not None
            ):
                self.type = "Amortissement"
                return 1

    def file_name(self, file):
        # Normalize the name to something meaningful.
        return "Boursorama.pdf"

    def file_account(self, file):
        """
        The function file_account() takes a file object as an argument and returns the account number
        associated with the file.

        :param file: the file to convert
        :return: The account number.
        """
        # Recherche du numéro de compte dans le fichier.
        text = file.convert(pdf_to_text)
        if self.type == "Compte":
            control = r"\s*(\d{11})"
        elif self.type == "CB":
            control = r"\s*((4979|4810)\*{8}\d{4})"
        elif self.type == "Amortissement":
            control = r"N(?:°|º) du crédit\s*:\s?(\d{5}\s?-\s?\d{11})"
        # Si debogage, affichage de l'extraction
        if self.debug:
            print(self.type)
        match = re.search(control, text)
        # Si debogage, affichage de l'extraction
        if self.debug:
            print(match.group(1))
        if match:
            compte = match.group(1)
            return self.accountList[compte]

    def file_date(self, file):
        """
        It takes a file object as an argument, converts it to text, and then searches for the date in the
        text. If it finds a date, it parses it and returns it as a datetime object.

        :param file: The file to convert
        :return: The date of the statement.
        """
        text = file.convert(pdf_to_text)
        match = re.search(r"(?:au\s*|Date départ\s*:\s)(\d*/\d*/\d*)", text)
        if match:
            return parse_datetime(match.group(1), dayfirst="True").date()

    def extract(self, file, existing_entries=None):

        # Nom du fichier tel qu'il sera renommé.
        document = str(self.file_date(file)) + " " + self.file_name(file)

        # Open the pdf file and convert it to text
        entries = []
        text = file.convert(pdf_to_text)

        # Si debogage, affichage de l'extraction
        if self.debug:
            print(text)
            print(self.type)

        if self.type == "Compte":
            # Identification du numéro de compte
            control = r"\s*\d{11}"
            match = re.search(control, text)
            if match:
                compte = match.group(0).split(" ")[-1]

            # Si debogage, affichage de l'extraction
            if self.debug:
                print(compte)

            # Affichage du solde initial
            control = r"SOLDE\s(?:EN\sEUR\s+)?AU\s:(\s+)(\d{1,2}\/\d{2}\/\d{4})(\s+)((?:\d{1,3}\.)?\d{1,3},\d{2})"
            match = re.search(control, text)
            if match:
                datebalance = parse_datetime(
                    match.group(2), dayfirst="True"
                ).date() + datetime.timedelta(1)
                longueur = (
                    len(match.group(1))
                    + len(match.group(3))
                    + len(match.group(2))
                    + len(match.group(4))
                )
                balance = match.group(4).replace(".", "").replace(",", ".")
                if longueur < 84:
                    # Si la distance entre les 2 champs est petite, alors, c'est un débit.
                    balance = "-" + balance

            # Si debogage, affichage de l'extraction
            #            if self.debug:
            #                print(self.type)
            #                print(datebalance)
            #                print(balance)
            #                print(longueur)

            meta = data.new_metadata(file.name, 0)
            meta["source"] = "pdfbourso"
            meta["document"] = document

            entries.append(
                data.Balance(
                    meta,
                    datebalance,
                    self.accountList[compte],
                    amount.Amount(D(balance), "EUR"),
                    None,
                    None,
                )
            )

            control = r"\d{1,2}\/\d{2}\/\d{4}\s(.*)\s(\d{1,2}\/\d{2}\/\d{4})\s(\s*)\s((?:\d{1,3}\.)?\d{1,3},\d{2})(?:(?:\n.\s{8,20})(.+?))?\n"  # regexr.com/4ju06
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

                ope["montant"] = chunk[3].replace(".", "").replace(",", ".")
                # Si debogage, affichage de l'extraction
                if self.debug:
                    print(ope["montant"])

                # Longueur de l'espace intercalaire
                longueur = (
                    len(chunk[0])
                    + len(chunk[1])
                    + len(chunk[2])
                    + len(chunk[3])
                )
                # Si debogage, affichage de l'extraction
                if self.debug:
                    print(longueur)

                if longueur > 148:
                    ope["type"] = "Credit"
                else:
                    ope["type"] = "Debit"
                    ope["montant"] = "-" + ope["montant"]
                # Si debogage, affichage de l'extraction
                if self.debug:
                    print(ope["montant"])

                ope["payee"] = re.sub(r"\s+", " ", chunk[0])
                # Si debogage, affichage de l'extraction
                if self.debug:
                    print(ope["payee"])

                ope["narration"] = re.sub(r"\s+", " ", chunk[4])
                # Si debogage, affichage de l'extraction
                if self.debug:
                    print(ope["narration"])

                # Creation de la transaction
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
                    date=parse_datetime(ope["date"], dayfirst="True").date(),
                    flag=flag,
                    payee=ope["payee"] or "inconnu",
                    narration=ope["narration"],
                    tags=data.EMPTY_SET,
                    links=data.EMPTY_SET,
                    postings=[posting_1],
                )
                entries.append(transac)

            # Recherche du solde final
            control = r"Nouveau solde en EUR :(\s+)((?:\d{1,3}\.)?(?:\d{1,3}\.)?\d{1,3},\d{2})"
            match = re.search(control, text)
            if match:
                balance = match.group(2).replace(".", "").replace(",", ".")
                longueur = len(match.group(1))
                if self.debug:
                    print(balance)
                    print(longueur)
                if longueur < 84:
                    # Si la distance entre les 2 champs est petite, alors, c'est un débit.
                    balance = "-" + balance
                # Recherche de la date du solde final
                control = r"(\d{1,2}\/\d{2}\/\d{4}).*40618"
                match = re.search(control, text)
                if match:
                    datebalance = parse_datetime(
                        match.group(1), dayfirst="True"
                    ).date()
                    if self.debug:
                        print(datebalance)
                    meta = data.new_metadata(file.name, 0)
                    meta["source"] = "pdfbourso"
                    meta["document"] = document

                    entries.append(
                        data.Balance(
                            meta,
                            datebalance,
                            self.accountList[compte],
                            amount.Amount(D(balance), "EUR"),
                            None,
                            None,
                        )
                    )

        if self.type == "Amortissement":
            # Identification du numéro de compte
            control = r"N(?:°|º) du crédit\s*:\s?(\d{5}\s?-\s?\d{11})"
            match = re.search(control, text)
            if match:
                compte = match.group(1)

            # Si debogage, affichage de l'extraction
            if self.debug:
                print(compte)

            control = r"(\d*/\d*/\d*)\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})"
            chunks = re.findall(control, text)

            # Si debogage, affichage de l'extraction
            if self.debug:
                print(chunks)

            index = 0
            for chunk in chunks:
                index += 1
                meta = data.new_metadata(file.name, index)
                meta["source"] = "pdfbourso"

                ope = dict()
                ope["date"] = parse_datetime(chunk[0], dayfirst="True").date()
                ope["prelevement"] = amount.Amount(
                    Decimal("-" + chunk[1].replace(",", ".")), "EUR"
                )
                ope["amortissement"] = amount.Amount(
                    Decimal(chunk[2].replace(",", ".")), "EUR"
                )
                ope["interet"] = amount.Amount(
                    Decimal(chunk[3].replace(",", ".")), "EUR"
                )
                ope["assurance"] = amount.Amount(
                    Decimal(chunk[4].replace(",", ".")), "EUR"
                )
                ope["CRD"] = amount.Amount(
                    Decimal("-" + str(chunk[7].replace(",", "."))), "EUR"
                )

                # Creation de la transactiocn
                posting_1 = data.Posting(
                    account="Actif:Boursorama:CCJoint",
                    units=ope["prelevement"],
                    cost=None,
                    flag=None,
                    meta=None,
                    price=None,
                )
                posting_2 = data.Posting(
                    account=self.accountList[compte],
                    units=ope["amortissement"],
                    cost=None,
                    flag=None,
                    meta=None,
                    price=None,
                )
                posting_3 = data.Posting(
                    account="Depenses:Banque:Interet",
                    units=ope["interet"],
                    cost=None,
                    flag=None,
                    meta=None,
                    price=None,
                )
                posting_4 = data.Posting(
                    account="Depenses:Banque:AssuEmprunt",
                    units=ope["assurance"],
                    cost=None,
                    flag=None,
                    meta=None,
                    price=None,
                )
                flag = flags.FLAG_OKAY
                transac = data.Transaction(
                    meta=meta,
                    date=ope["date"],
                    flag=flag,
                    payee="ECH PRET:8028000060686223",
                    narration="",
                    tags=data.EMPTY_SET,
                    links=data.EMPTY_SET,
                    postings=[posting_1, posting_2, posting_3, posting_4],
                )
                entries.append(transac)
                entries.append(
                    data.Balance(
                        meta,
                        ope["date"] + datetime.timedelta(1),
                        self.accountList[compte],
                        ope["CRD"],
                        None,
                        None,
                    )
                )

        if self.type == "CB":
            # Identification du numéro de compte
            control = r"\s*((4979|4810)\*{8}\d{4})"
            match = re.search(control, text)
            if match:
                compte = match.group(1)

            # Si debogage, affichage de l'extraction
            if self.debug:
                print(compte)

            control = r"(\d{1,2}\/\d{2}\/\d{4})\s*CARTE\s(.*)\s((?:\d{1,3}\.)?\d{1,3},\d{2})"
            chunks = re.findall(control, text)

            # Si debogage, affichage de l'extraction
            if self.debug:
                print(control)
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

                ope["date"] = chunk[0]
                # Si debogage, affichage de l'extraction
                if self.debug:
                    print(ope["date"])

                ope["montant"] = "-" + chunk[2].replace(".", "").replace(
                    ",", "."
                )
                # Si debogage, affichage de l'extraction
                if self.debug:
                    print(ope["montant"])

                ope["payee"] = re.sub(r"\s+", " ", chunk[1])
                # Si debogage, affichage de l'extraction
                if self.debug:
                    print(ope["payee"])

                # Creation de la transaction
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
                    date=parse_datetime(ope["date"], dayfirst="True").date(),
                    flag=flag,
                    payee=ope["payee"] or "inconnu",
                    narration=None,
                    tags=data.EMPTY_SET,
                    links=data.EMPTY_SET,
                    postings=[posting_1],
                )
                entries.append(transac)

            # Recherche du solde final
            control = r"A VOTRE DEBIT LE\s(\d{1,2}\/\d{2}\/\d{4})\s*((?:\d{1,3}\.)?(?:\d{1,3}\.)?\d{1,3},\d{2})"
            match = re.search(control, text)
            if match:
                balance = "-" + match.group(2).replace(".", "").replace(
                    ",", "."
                )
                if self.debug:
                    print(balance)
                # Recherche de la date du solde final
                control = r"(\d{1,2}\/\d{2}\/\d{4}).*40618"
                match = re.search(control, text)
                if match:
                    datebalance = parse_datetime(
                        match.group(1), dayfirst="True"
                    ).date()
                    if self.debug:
                        print(datebalance)
                    meta = data.new_metadata(file.name, 0)
                    meta["source"] = "pdfbourso"
                    meta["document"] = document

                    entries.append(
                        data.Balance(
                            meta,
                            datebalance,
                            self.accountList[compte],
                            amount.Amount(D(balance), "EUR"),
                            None,
                            None,
                        )
                    )

        return entries
