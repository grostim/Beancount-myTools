"""Importer pour Generali Assurance Vie.
Cet importer est associé au script d'import qui génère des fichiers json
pour chaque opération.
"""


import re
import datetime
import json
from os import path
from dateutil.parser import parse as parse_datetime
from beancount.core import amount, position, data, flags
from beancount.ingest import importer
from beancount.core.number import Decimal, D

class jsongenerali(importer.ImporterProtocol):
    """Importer pour Generali Assurance Vie.."""

    def __init__(
        self,
        accountList,
        debug: bool = False,
        compteTiers="Actif:FIXME",
        compteFrais="Depenses:FIXME",
        compteDividendes="Revenus:FIXME",
    ):
        assert isinstance(
            accountList, dict
        ), "La liste de comptes doit etre un type dict"
        self.accountList = accountList
        self.debug = debug
        self.compteTiers = compteTiers
        self.compteFrais = compteFrais
        self.compteDividendes = compteDividendes

    def identify(self, file):
        return re.match(r".*.json", path.basename(file.name))

    def file_account(self, file):
        with open(file.name, "r") as read_file:
            jsondata = json.load(read_file)

            # Si debogage, affichage de l'extraction
            if self.debug:
                print(jsondata["compte"])

            return self.accountList[jsondata["compte"]]

    def file_name(self, file):
        return format(re.sub("\d{4}-\d{2}-\d{2}-", "", path.basename(file.name)))

    def file_date(self, file):

        # Si debogage, affichage de l'extraction
        if self.debug:
            print(re.search("(\d{4}-\d{2}-\d{2})-", path.basename(file.name)))

        return parse_datetime(
            re.search("(\d{4}-\d{2}-\d{2})-", path.basename(file.name)).group(1)
        ).date()
    
    def balayageJSONtable():
        """Une procédure qui balaye toutes les lignes du JSON"""
        postings = []
        total = 0
        for ligne in jsondata["table"]:
            # Si debogage, affichage de l'extraction
            if self.debug:
                print(ligne)

            postings.append(
                data.Posting(
                    account=self.accountList[jsondata["compte"]]
                    + ":"
                    + ligne["isin"],
                    units=amount.Amount(
                        Decimal(
                            ligne["nbpart"]
                            .replace(",", ".")
                            .replace(" ", "")
                            .replace("\xa0", "")
                        ),
                        ligne["isin"],
                    ),
                    cost=position.Cost(
                        Decimal(
                            ligne["valeurpart"]
                            .replace(",", ".")
                            .replace(" ", "")
                            .replace("\xa0", "")
                        ),
                        ligne["date"],
                        None,
                        None,
                    ),
                    flag=None,
                    meta=None,
                    price=None,
                )
            )
            total = total + Decimal(
                ligne["montant"]
                .replace(",", ".")
                .replace(" ", "")
                .replace("\xa0", "")
            )
            
    def extract(self, file, existing_entries=None):
        entries = []
        with open(file.name, "r") as read_file:
            jsondata = json.load(read_file)
            # Si debogage, affichage de l'extraction
            if self.debug:
                print(jsondata["ope"])

            if jsondata["ope"] == "prélèvement" or jsondata["ope"] == "Versement Libre":
                
                balayageJSONtable()

                # On crée la dernière transaction.
                postings.append(
                    data.Posting(
                        account=self.compteTiers,
                        units=amount.Amount(Decimal(str(total)), "EUR"),
                        cost=None,
                        flag=None,
                        meta=None,
                        price=None,
                    )
                )
                meta = data.new_metadata(file.name, 0)
                meta["source"] = "jsongenerali"
                flag = flags.FLAG_OKAY
                transac = data.Transaction(
                    meta=meta,
                    date=parse_datetime(
                        re.search(
                            "(\d{4}-\d{2}-\d{2})-", path.basename(file.name)
                        ).group(1)
                    ).date(),
                    flag=flag,
                    payee=jsondata["ope"] + " Generali",
                    narration=None,
                    tags=data.EMPTY_SET,
                    links=data.EMPTY_SET,
                    postings=postings,
                )
                entries.append(transac)

            if jsondata["ope"] == "Frais de gestion":
                balayageJSONtable()
                # On crée la dernière transaction.
                postings.append(
                    data.Posting(
                        account=self.compteDividende,
                        units=amount.Amount(Decimal(str(total)), "EUR"),
                        cost=None,
                        flag=None,
                        meta=None,
                        price=None,
                    )
                )               

        return entries
