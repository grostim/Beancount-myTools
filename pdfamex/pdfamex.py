"""Importer for PDF statements from AmericanExpress.
"""
__copyright__ = (
    "Copyright (C) 2016  Martin Blais / Mofified in 2019 by Grostim"
)
__license__ = "GNU GPLv2"

import re
import subprocess
import datetime
from myTools.myutils import pdf_to_text, traduire_mois
from dateutil.parser import parse as parse_datetime
from beancount.core import amount, data, flags
from beancount.ingest import importer
from beancount.core.number import Decimal


class pdfamex(importer.ImporterProtocol):
    """An importer for Boursorama PDF statements."""

    def __init__(
        self,
        accountList,
        debug: bool = False,
    ):
        assert isinstance(
            accountList, dict
        ), "La liste de comptes doit etre un type dict"
        self.accountList = accountList
        self.debug = debug

    def identify(self, file):
        if file.mimetype() != "application/pdf":
            return False

        # Look for some words in the PDF file to figure out if it's a statement
        # from ACME. The filename they provide (Statement.pdf) isn't useful.On considéère que c'est un relevé Boursorama si on trouve le mot "BOURSORAMA" dedans.
        text = file.convert(pdf_to_text)
        if text:
            return re.search("Carte Air France KLM", text) is not None

    def file_name(self, file):
        # Normalize the name to something meaningful.
        return "Amex.pdf"

    def file_account(self, file):
        # Recherche du numéro de compte dans le fichier.
        text = file.convert(pdf_to_text)
        control = r"xxxx-xxxxxx-\d{5}"
        match = re.search(control, text)
        if match:
            compte = match.group(0).split(" ")[-1]
            return self.accountList[compte]

    def file_date(self, file):
        # Get the actual statement's date from the contents of the file.
        text = file.convert(pdf_to_text)
        match = re.search(
            r"xxxx-xxxxxx-\d{5}\s*(\d*/\d*/\d*)", text
        )  # regexr.com/4jprk
        if match:
            return parse_datetime(match.group(1), dayfirst="True").date()

    def check_before_add(self, transac):
        try:
            data.sanity_check_types(transac)
        except AssertionError:
            self.logger.exception("Transaction %s not valid", transac)

    def extract(self, file, existing_entries=None):
        entries = []
        text = file.convert(pdf_to_text)

        if self.debug:
            print(text)

        statement_date = self._extract_statement_date(text)
        account_number = self._extract_account_number(text)
        transactions = self._extract_transactions(text, statement_date)

        for index, transaction in enumerate(transactions, start=1):
            entries.append(self._create_transaction_entry(file, index, transaction, account_number))

        balance_entry = self._create_balance_entry(file, text, account_number)
        entries.append(balance_entry)

        return entries

    def _extract_statement_date(self, text):
        match = re.search(r"xxxx-xxxxxx-\d{5}\s*(\d*/(\d*)/(\d*))", text)
        if not match:
            raise ValueError("Date du relevé non trouvée")
        return {
            'full': match.group(1),
            'month': match.group(2),
            'year': match.group(3)
        }

    def _extract_account_number(self, text):
        match = re.search(r"xxxx-xxxxxx-\d{5}", text)
        if not match:
            raise ValueError("Numéro de compte non trouvé")
        return match.group(0)

    def _extract_transactions(self, text, statement_date):
        control = r"\d{1,2}\s[a-zéèûôùê]{3,4}\s*\d{1,2}\s[a-zéèûôùê]{3,4}.*\d+,\d{2}(?:\s*CR)?"  # regexr.com/4jqdk
        chunks = re.findall(control, text)
        return chunks

    def _create_transaction_entry(self, file, index, transaction, account_number):
        meta = data.new_metadata(file.name, index)
        meta["source"] = "pdfamex"
        
        posting = data.Posting(
            account=self.accountList[account_number],
            units=transaction['amount'],
            cost=None,
            flag=None,
            meta=None,
            price=None
        )

        return data.Transaction(
            meta=meta,
            date=transaction['date'].date(),
            flag=flags.FLAG_OKAY,
            payee=transaction['payee'] or "inconnu",
            narration="",
            tags=data.EMPTY_SET,
            links=data.EMPTY_SET,
            postings=[posting]
        )

    def _create_balance_entry(self, file, text, account_number):
        control = r"Total des dépenses pour\s+(?:.*?)\s+(\d{0,3}\s{0,1}\d{1,3},\d{2})"
        match = re.search(control, text)
        montant = -1 * Decimal(
            match.group(1).replace(",", ".").replace(" ", "")
        )

        meta = data.new_metadata(file.name, index)
        meta["source"] = "pdfamex"
        #        meta["statementExtract"] = match.group(0)

        # Si debogage, affichage de l'extraction
        if self.debug:
            print(montant)

        match = re.search(
            r"xxxx-xxxxxx-\d{5}\s*(\d*/\d*/\d*)", text
        )  # regexr.com/4jprk
        balancedate = parse_datetime(
            match.group(1), dayfirst="True"
        ).date() + datetime.timedelta(1)

        # Si debogage, affichage de l'extraction
        if self.debug:
            print(balancedate)

        return data.Balance(
            meta,
            balancedate,
            self.accountList[compte],
            amount.Amount(montant, "EUR"),
            None,
            None,
        )
