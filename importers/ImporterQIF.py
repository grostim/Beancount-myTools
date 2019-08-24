# coding=utf-8

"""
A simple class to parse a Quicken (QIF) file to beancount.
Version originale par PFrancois: https://github.com/pfrancois/beancount_scripts/blob/master/importers/fp_importer_beancount/import_qif.py
Modifiée par GrosTim pour s'adapter aux comptes boursorama.
"""

import sys
import datetime
import logging
import re
from os import path
#import decimal

from beancount.core import amount
from beancount.core import data  # pylint:disable=E0611
from beancount.core import flags
from beancount.core.number import MISSING
from beancount.ingest import importer
from beancount.core.number import Decimal

NoneType = type(None)


class ImporterQIF(importer.ImporterProtocol):

    def __init__(self,accountList):
        self.logger = logging.getLogger(__file__)  # pylint: disable=W0612
        assert isinstance(accountList, dict), "La liste de comptes doit etre un type dict"
        self.accountList=accountList

    def identify(self, file):
        return re.match(r".*.qif", path.basename(file.name))

    def file_account(self, file):
        return self.accountList[re.sub("\s?(\(\d*\))?.qif","",path.basename(file.name))] #regexr.com/4jp6b

    def file_name(self, file):
        return format(path.basename(file.name))

    def file_date(self, file):
        with open(file.name, "r", encoding="windows-1250") as fichier:
            chunks = fichier.read().split("\n^\n")
            lines = chunks[-2].split("\n")
            return datetime.datetime.strptime(lines[-3][1:], "%d/%m/%Y").date()

    def check_before_add(self, transac):
        try:
            data.sanity_check_types(transac)
        except AssertionError:
            self.logger.exception("Transaction %s not valid", transac)

    def extract(self, file, existing_entries=None):
        # Open the CSV file and create directives.
        entries = []
        with open(file.name, "r", encoding="windows-1250") as fichier:
            chunks = fichier.read().split("\n^\n")
            index = 0
            for chunk in chunks:
                index += 1
                meta = data.new_metadata(file.name, index)
                meta["source"] = "qif"
#		A supprimer car fait planter le test de regression
#                meta["dateImport"] = str(datetime.datetime.now())
                ope = dict()
                first_line = chunk.split("\n")[0]
                if first_line == "!Account":
                    continue
                if len(chunk) == 0:
                    continue
                for line in chunk.split("\n"):
                    if line[0] == "!":
                        continue
                    if line[0] == "D":
                        ope["date"] = datetime.datetime.strptime(line[1:], "%d/%m/%Y")
                    if line[0] == "T":
                        ope["montant"] = amount.Amount(Decimal(line[1:].replace(",", '')), "EUR")
                    if line[0] == "P":
                        ope["tiers"] = line[1:]
                        ope["cat"] = "Depenses:A-CLASSER"
#                    if line[0] == "L":
#                        if line[1] == "[":
#                            ope["tiers"] = "Virement"
#                            ope["cat"] = "Assets:Banque:,%s" % line[2:-1]
#                        else:
#                            ope["cat"] = "Expenses:%s" % {line[1:]}
                posting_1 = data.Posting(
                    account=self.accountList[path.basename(file.name).replace(".qif",'')],
                    units=ope["montant"],
                    cost=None,
                    flag=None,
                    meta=None,
                    price=None,
                )
                posting_2 = data.Posting(
                    account=ope["cat"],
                    units=amount.Amount(ope["montant"].number * -1, "EUR"),
                    cost=None,
                    flag=None,
                    meta=None,
                    price=None,
                )
                flag = flags.FLAG_WARNING
                transac = data.Transaction(
                    meta=meta,
                    date=ope["date"].date(),
                    flag=flag,
                    payee=ope["tiers"] or "inconnu",
                    narration="",
                    tags=data.EMPTY_SET,
                    links=data.EMPTY_SET,
                    postings=[posting_1, posting_2],
                )
                entries.append(transac)
        return entries
