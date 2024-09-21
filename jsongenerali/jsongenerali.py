"""Importer pour Generali Assurance Vie.
Cet importer est associé au script d'import qui génère des fichiers json
pour chaque opération.
"""

import re
import json
from os import path
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional
from dateutil.parser import parse as parse_datetime
from beancount.core import amount, position, data, flags
from beancount.ingest import importer

class JSONGenerali(importer.ImporterProtocol):
    """Importateur pour Generali Assurance Vie."""

    def __init__(
        self,
        account_list: Dict[str, str],
        debug: bool = False,
        compte_tiers: str = "Actif:FIXME",
        compte_frais: str = "Depenses:FIXME",
        compte_dividendes: str = "Revenus:FIXME",
    ):
        """
        Initialise l'importateur JSONGenerali.

        Args:
            account_list (Dict[str, str]): Dictionnaire associant les comptes Generali aux comptes Beancount.
            debug (bool, optional): Active le mode debug si True. Par défaut False.
            compte_tiers (str, optional): Compte pour les transactions avec des tiers.
            compte_frais (str, optional): Compte pour les frais.
            compte_dividendes (str, optional): Compte pour les dividendes.
        """
        self.account_list = account_list
        self.debug = debug
        self.compte_tiers = compte_tiers
        self.compte_frais = compte_frais
        self.compte_dividendes = compte_dividendes

    def _debug(self, message: str):
        """Affiche un message de débogage si le mode debug est activé."""
        if self.debug:
            print(f"[DEBUG] {message}")

    def identify(self, file) -> bool:
        """Identifie si le fichier est un relevé Generali JSON."""
        return bool(re.match(r".*.generali.json", path.basename(file.name)))

    def file_account(self, file) -> Optional[str]:
        """Extrait le compte associé au fichier."""
        with open(file.name, "r") as read_file:
            jsondata = json.load(read_file)
            self._debug(f"Compte extrait: {jsondata['compte']}")
            return self.account_list.get(jsondata["compte"])

    def file_name(self, file) -> str:
        """Retourne le nom du fichier pour le relevé."""
        return re.sub(r"\d{4}-\d{2}-\d{2}-", "", path.basename(file.name))

    def file_date(self, file):
        """Extrait la date du relevé."""
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})-", path.basename(file.name))
        self._debug(f"Date extraite: {date_match.group(1) if date_match else 'Non trouvée'}")
        return parse_datetime(date_match.group(1)).date() if date_match else None

    def _parse_decimal(self, value: str) -> Decimal:
        """Parse une chaîne en Decimal en gérant les différents formats."""
        return Decimal(value.replace(",", ".").replace(" ", "").replace("\xa0", "").replace(r"\u00a", ""))

    def _round_decimal(self, value: Decimal) -> Decimal:
        """Arrondit une valeur Decimal à 4 décimales."""
        return value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

    def _create_posting(self, account: str, montant: str, devise: str, cost: Optional[position.Cost] = None, price: Optional[amount.Amount] = None) -> data.Posting:
        """
        Crée un posting Beancount avec price et cost arrondis à 4 décimales.

        Args:
            account (str): Le compte associé au posting.
            montant (str): Le montant du posting.
            devise (str): La devise du posting.
            cost (Optional[position.Cost]): Le coût associé, si applicable.
            price (Optional[amount.Amount]): Le prix associé, si applicable.

        Returns:
            data.Posting: Le posting Beancount créé.
        """
        units = amount.Amount(self._parse_decimal(montant), devise)

        if cost:
            cost = position.Cost(
                self._round_decimal(cost.number),
                cost.currency,
                cost.date,
                cost.label
            )

        if price:
            price = amount.Amount(
                self._round_decimal(price.number),
                price.currency
            )

        return data.Posting(
            account=account,
            units=units,
            cost=cost,
            price=price,
            flag=None,
            meta=None
        )

    def _process_transaction(self, jsondata: Dict, file) -> data.Transaction:
        """Traite une transaction et retourne une directive Transaction Beancount."""
        postings = []
        total = Decimal(0)

        for ligne in jsondata["table"]:
            self._debug(f"Ligne traitée: {ligne}")
            
            if not ligne["valeurpart"]:
                ligne["valeurpart"] = "1.00"
                ligne["nbpart"] = ligne["montant"]

            montant = self._parse_decimal(ligne["montant"])
            nb_parts = self._parse_decimal(ligne["nbpart"])
            valeur_part = montant / nb_parts

            cost = position.Cost(self._round_decimal(valeur_part), "EUR", None, None) if nb_parts > 0 else None
            price = amount.Amount(self._round_decimal(abs(valeur_part)), "EUR")
            postings.append(self._create_posting(
                f"{self.account_list[jsondata['compte']]}:{ligne['isin'].replace(' ', '').upper()}",
                ligne["nbpart"],
                ligne["isin"].replace(" ", "").upper(),
                cost,
                price
            ))
            total += montant

        if jsondata["ope"] in ["prélèvement", "Versement Libre"]:
            postings.append(self._create_posting(self.compte_tiers, str(-total), "EUR"))
        elif jsondata["ope"] == "Frais de gestion":
            postings.append(self._create_posting(self.compte_frais, str(total), "EUR"))
        elif jsondata["ope"] == "Distribution de dividendes":
            postings.append(self._create_posting(self.compte_dividendes, str(-total), "EUR"))

        return data.Transaction(
            meta=data.new_metadata(file.name, 0, {"source": "jsongenerali"}),
            date=self.file_date(file),
            flag=flags.FLAG_OKAY,
            payee=f"{jsondata['ope']} Generali",
            narration=None,
            tags=data.EMPTY_SET,
            links=data.EMPTY_SET,
            postings=postings
        )

    def extract(self, file, existing_entries=None) -> List[data.Directive]:
        """Extrait les transactions du relevé JSON Generali."""
        entries = []
        with open(file.name, "r") as read_file:
            jsondata = json.load(read_file)
            self._debug(f"Opération extraite: {jsondata['ope']}")

            if jsondata["ope"] in ["prélèvement", "Versement Libre", "Frais de gestion", "Distribution de dividendes", "Arbitrage", "Opération sur titres"]:
                entries.append(self._process_transaction(jsondata, file))
            else:
                self._debug(f"{path.basename(file.name)} : Type de relevé inconnu")

        return entries
