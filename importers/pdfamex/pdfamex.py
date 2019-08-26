"""Importer for PDF statements from AmericanExpress.
"""
__copyright__ = "Copyright (C) 2016  Martin Blais / Mofified in 2019 by Grostim"
__license__ = "GNU GPLv2"

import re
import subprocess
import datetime
from dateutil.parser import parse as parse_datetime
from beancount.core import amount, data, flags
from beancount.ingest import importer
from beancount.core.number import Decimal

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

def traduire_mois(str):
    str = str.replace('fév', 'feb')
    str = str.replace('mars', 'mar')
    str = str.replace('avr', 'apr')
    str = str.replace('mai', 'may')
    str = str.replace('juin', 'jun')
    str = str.replace('juil', 'jul')
    str = str.replace('août', 'aug')
    str = str.replace('déc', 'dec')
    return str


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


class pdfamex(importer.ImporterProtocol):
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
            return re.search('Carte Air France KLM', text) is not None

    def file_name(self, file):
        # Normalize the name to something meaningful.
        return 'Amex.pdf'

    def file_account(self, file):
        #Recherche du numéro de compte dans le fichier.
        text = file.convert(pdf_to_text)
        control='xxxx-xxxxxx-\d{5}'
        match = re.search(control, text)
        if match:
            compte = match.group(0).split(' ')[-1]
            return self.accountList[compte]

    def file_date(self, file):
        # Get the actual statement's date from the contents of the file.
        text = file.convert(pdf_to_text)
        match = re.search('xxxx-xxxxxx-\d{5}\s*(\d*/\d*/\d*)', text) #regexr.com/4jprk
        if match:
            return parse_datetime(match.group(1),dayfirst="True").date()

    def check_before_add(self, transac):
        try:
            data.sanity_check_types(transac)
        except AssertionError:
            self.logger.exception("Transaction %s not valid", transac)

    def extract(self, file, existing_entries=None):
        # Open the pdf file and create directives.
        entries = []
        text = file.convert(pdf_to_text)

        # Si debogage, affichage de l'extraction  
        if self.debug:
            print(text)

        # On relève d'abord la date du rapport
        control = 'xxxx-xxxxxx-\d{5}\s*\d*/(\d*)/(\d*)'
        match = re.search(control, text)
        statementmonth = match.group(1)
        statementyear = match.group(2)

        # Et le numéro de compte
        control='xxxx-xxxxxx-\d{5}'
        match = re.search(control, text)
        if match:
            compte = match.group(0).split(' ')[-1]

        control='\d{1,2}\s[a-zéèûôùê]{3,4}\s*\d{1,2}\s[a-zéèûôùê]{3,4}.*\d+,\d{2}(?:\s*CR)?' #regexr.com/4jqdk
        chunks = re.findall(control, text)

        # Si debogage, affichage de l'extraction
        if self.debug:
            print(chunks)

        index = 0
        for chunk in chunks:
            index += 1
            meta = data.new_metadata(file.name, index)
            meta["source"] = "pdfamex"
            meta["statementExtract"] = chunk
            ope = dict()
            ope={}

            # Si debogage, affichage de l'extraction
            if self.debug:
                print(chunk)

            # A la recherche de la date.
            match = re.search('(\d{1,2}\s[a-zéèûôùê]{3,4})\s*(\d{1,2}\s[a-zéèûôùê]{3,4})',chunk)
            rawdate = match.group(2) #On extrait la seconde date de la ligne.

            # Si debogage, affichage de l'extraction
            if self.debug:
                print(rawdate)
            
            match = re.search('\d{1,2}\s[a-zéèûôùê]{3,4}\s*\d{1,2}\s([a-zéèûôùê]{3,4})',chunk)

            # Si debogage, affichage de l'extraction
            if self.debug:
                print(match.group(1))

            if match.group(1) == "déc" and statementmonth == "01":
                ope["date"] = parse_datetime(traduire_mois(rawdate + " 20" + str(int(statementyear)-1)))
            else:
                ope["date"] = parse_datetime(traduire_mois(rawdate + " 20" + statementyear))

            # A la recherche du montant.
            # TODO: Ca merde si valeur en devise >999 . Voir Sept 2018.
            control='\d{1,2}\s[a-zéèûôùê]{3,4}\s*\d{1,2}\s[a-zéèûôùê]{3,4}\s+(.*?)\s+(\d{0,3}\s{0,1}\d{1,3},\d{2})(\s*CR)?'
            match = re.search(control, chunk)

            # Recherche de "CR" si Crédit.
            if match.group(3) is not None:
                meta["type"] = "Débit"
                ope["montant"] = amount.Amount(1 * Decimal(match.group(2).replace(",", '.').replace(" ", '')), "EUR")
            else:
                meta["type"] = "Credit"
                ope["montant"] = amount.Amount(-1 * Decimal(match.group(2).replace(",", '.').replace(" ", '')), "EUR")
            # Recherche du Payee

            ope["tiers"] = re.sub("\s+"," ",match.group(1))
            # Et on rajoute la transaction
            posting_1 = data.Posting(
                account=self.accountList[compte],
                units=ope["montant"],
                cost=None,
                flag=None,
                meta=None,
                price=None,
            )
            flag = flags.FLAG_OKAY
            transac = data.Transaction(
                meta=meta,
                date=ope["date"].date(),
                flag=flag,
                payee=ope["tiers"] or "inconnu",
                narration="",
                tags=data.EMPTY_SET,
                links=data.EMPTY_SET,
                postings=[posting_1],
                )
            entries.append(transac)
 
        #A la recherche de la balance:
        control='Total des dépenses pour\s+(?:.*?)\s+(\d{0,3}\s{0,1}\d{1,3},\d{2})'
        match = re.search(control, text)
        montant = -1 * Decimal(match.group(1).replace(",", '.').replace(" ", ''))

        meta = data.new_metadata(file.name, index)
        meta["source"] = "pdfamex"
        meta["statementExtract"] = match.group(0)

        # Si debogage, affichage de l'extraction
        if self.debug:
            print(montant)

        match = re.search('xxxx-xxxxxx-\d{5}\s*(\d*/\d*/\d*)', text) #regexr.com/4jprk
        balancedate = parse_datetime(match.group(1),dayfirst="True").date() + datetime.timedelta(1)

        # Si debogage, affichage de l'extraction
        if self.debug:
            print(balancedate)

        entries.append(
            data.Balance(meta, balancedate,
                         self.accountList[compte], amount.Amount(montant, "EUR"),
                         None, None))
        return entries 
