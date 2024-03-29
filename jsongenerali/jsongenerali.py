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
        return re.match(r".*.generali.json", path.basename(file.name))

    def file_account(self, file):
        with open(file.name, "r") as read_file:
            jsondata = json.load(read_file)

            # Si debogage, affichage de l'extraction
            if self.debug:
                print(jsondata["compte"])

            return self.accountList[jsondata["compte"]]

    def file_name(self, file):
        return format(
            re.sub(r"\d{4}-\d{2}-\d{2}-", "", path.basename(file.name))
        )

    def file_date(self, file):

        # Si debogage, affichage de l'extraction
        if self.debug:
            print(re.search(r"(\d{4}-\d{2}-\d{2})-", path.basename(file.name)))

        return parse_datetime(
            re.search(r"(\d{4}-\d{2}-\d{2})-", path.basename(file.name)).group(
                1
            )
        ).date()

    def balayageJSONtable(self, jsondata, afficherCost: bool = False):
        """Une procédure qui balaye toutes les lignes du JSON"""
        self.postings = []
        self.total = 0
        for ligne in jsondata["table"]:
            # Si debogage, affichage de l'extraction
            if self.debug:
                print(ligne)
                print(parse_datetime(ligne["date"]).date)

            if ligne["valeurpart"] == "":
                ligne["valeurpart"] = "1.00"
                ligne["nbpart"] = ligne["montant"]

            if afficherCost and re.match("-", ligne["nbpart"]) is None:
                cost = position.Cost(
                    Decimal(
                        float(
                            ligne["montant"]
                            .replace(",", ".")
                            .replace(" ", "")
                            .replace("\xa0", "")
                            .replace(r"\u00a", "")
                        )
                        / float(
                            ligne["nbpart"]
                            .replace(",", ".")
                            .replace(" ", "")
                            .replace("\xa0", "")
                            .replace(r"\u00a", "")
                        )
                    ).quantize(Decimal(".0001")),
                    "EUR",
                    None,
                    None,
                )
            else:
                cost = None

            self.postings.append(
                data.Posting(
                    account=self.accountList[jsondata["compte"]]
                    + ":"
                    + ligne["isin"].replace(" ", "").upper(),
                    units=amount.Amount(
                        Decimal(
                            ligne["nbpart"]
                            .replace(",", ".")
                            .replace(" ", "")
                            .replace("\xa0", "")
                            .replace(r"\u00a", "")
                        ),
                        ligne["isin"].replace(" ", "").upper(),
                    ),
                    cost=cost,
                    flag=None,
                    meta=None,
                    price=amount.Amount(
                        Decimal(
                            abs(
                                float(
                                    ligne["montant"]
                                    .replace(",", ".")
                                    .replace(" ", "")
                                    .replace("\xa0", "")
                                    .replace(r"\u00a", "")
                                )
                                / float(
                                    ligne["nbpart"]
                                    .replace(",", ".")
                                    .replace(" ", "")
                                    .replace("\xa0", "")
                                    .replace(r"\u00a", "")
                                )
                            )
                        ).quantize(Decimal(".0001")),
                        "EUR",
                    ),
                )
            )
            self.total = self.total + Decimal(
                ligne["montant"]
                .replace(",", ".")
                .replace(" ", "")
                .replace("\xa0", "")
                .replace(r"\u00a", "")
            )

    def extract(self, file, existing_entries=None):
        entries = []
        with open(file.name, "r") as read_file:
            jsondata = json.load(read_file)
            # Si debogage, affichage de l'extraction
            if self.debug:
                print(jsondata["ope"])

            if (
                jsondata["ope"] == "prélèvement"
                or jsondata["ope"] == "Versement Libre"
            ):

                self.balayageJSONtable(jsondata, afficherCost=True)

                # On crée la dernière transaction.
                self.postings.append(
                    data.Posting(
                        account=self.compteTiers,
                        units=amount.Amount(
                            Decimal("-" + str(self.total)), "EUR"
                        ),
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
                            r"(\d{4}-\d{2}-\d{2})-", path.basename(file.name)
                        ).group(1)
                    ).date(),
                    flag=flag,
                    payee=jsondata["ope"] + " Generali",
                    narration=None,
                    tags=data.EMPTY_SET,
                    links=data.EMPTY_SET,
                    postings=self.postings,
                )
                entries.append(transac)

            elif jsondata["ope"] == "Frais de gestion":
                self.balayageJSONtable(jsondata, afficherCost=True)
                # On crée la dernière transaction.
                self.postings.append(
                    data.Posting(
                        account=self.compteFrais,
                        units=amount.Amount(Decimal(str(self.total)), "EUR"),
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
                            r"(\d{4}-\d{2}-\d{2})-", path.basename(file.name)
                        ).group(1)
                    ).date(),
                    flag=flag,
                    payee=jsondata["ope"] + " Generali",
                    narration=None,
                    tags=data.EMPTY_SET,
                    links=data.EMPTY_SET,
                    postings=self.postings,
                )
                entries.append(transac)

            elif jsondata["ope"] == "Distribution de dividendes":
                self.balayageJSONtable(jsondata, afficherCost=True)
                # On crée la dernière transaction.
                self.postings.append(
                    data.Posting(
                        account=self.compteDividendes,
                        units=amount.Amount(
                            Decimal("-" + str(self.total)), "EUR"
                        ),
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
                            r"(\d{4}-\d{2}-\d{2})-", path.basename(file.name)
                        ).group(1)
                    ).date(),
                    flag=flag,
                    payee=jsondata["ope"] + " Generali",
                    narration=None,
                    tags=data.EMPTY_SET,
                    links=data.EMPTY_SET,
                    postings=self.postings,
                )
                entries.append(transac)

            elif jsondata["ope"] == "Arbitrage" or "Opération sur titres":
                self.balayageJSONtable(jsondata, afficherCost=True)
                meta = data.new_metadata(file.name, 0)
                meta["source"] = "jsongenerali"
                flag = flags.FLAG_OKAY
                transac = data.Transaction(
                    meta=meta,
                    date=parse_datetime(
                        re.search(
                            r"(\d{4}-\d{2}-\d{2})-", path.basename(file.name)
                        ).group(1)
                    ).date(),
                    flag=flag,
                    payee=jsondata["ope"] + " Generali",
                    narration=None,
                    tags=data.EMPTY_SET,
                    links=data.EMPTY_SET,
                    postings=self.postings,
                )
                entries.append(transac)

            else:
                print(path.basename(file.name) + " : Type de relevé inconnu")
        return entries
