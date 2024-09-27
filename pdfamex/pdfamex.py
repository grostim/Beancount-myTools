"""Importateur pour les relevés PDF d'American Express."""

import re
from datetime import timedelta, datetime
from decimal import Decimal
from typing import List, Dict, Optional
from functools import lru_cache

from dateutil.parser import parse as parse_datetime
from beancount.core import amount, data, flags
from beancount.ingest import importer
from ..myutils import pdf_to_text, traduire_mois



class PDFAmex(importer.ImporterProtocol):
    """
    Importateur pour les relevés PDF American Express.

    Cette classe permet d'extraire les transactions et le solde des relevés
    American Express au format PDF et de les convertir en entrées Beancount.

    Attributes:
        ACCOUNT_NUMBER_PATTERN (str): Motif regex pour extraire le numéro de compte.
        STATEMENT_DATE_PATTERN (str): Motif regex pour extraire la date du relevé.
        TRANSACTION_PATTERN (str): Motif regex pour identifier les transactions.
        TRANSACTION_DATE_PATTERN (str): Motif regex pour extraire les dates des transactions.
        TRANSACTION_DETAILS_PATTERN (str): Motif regex pour extraire les détails des transactions.
        BALANCE_PATTERN (str): Motif regex pour extraire le solde total.
    """

    ACCOUNT_NUMBER_PATTERN = r"xxxx-xxxxxx-(\d{5})"
    STATEMENT_DATE_PATTERN = r"xxxx-xxxxxx-\d{5}\s*(\d*/\d*/\d*)"
    TRANSACTION_PATTERN = r"\d{1,2}\s[a-zéèûôùê]{3,4}\s*\d{1,2}\s[a-zéèûôùê]{3,4}.*\d+,\d{2}(?:\s*CR)?"
    TRANSACTION_DATE_PATTERN = (
        r"(\d{1,2}\s[a-zéèûôùê]{3,4})\s*(\d{1,2}\s[a-zéèûôùê]{3,4})"
    )
    TRANSACTION_DETAILS_PATTERN = r"\d{1,2}\s[a-zéèûôùê]{3,4}\s*\d{1,2}\s[a-zéèûôùê]{3,4}\s+(.*?)\s+(\d{0,3}\s{0,1}\d{1,3},\d{2})(\s*CR)?$"
    BALANCE_PATTERN = (
        r"Total des dépenses pour\s+(?:.*?)\s+(\d{0,3}\s{0,1}\d{1,3},\d{2})"
    )

    def __init__(self, account_list: Dict[str, str], debug: bool = False):
        """
        Initialise l'importateur PDFAmex.

        Args:
            account_list (Dict[str, str]): Dictionnaire associant les numéros de compte aux noms de compte.
            debug (bool, optional): Active le mode debug si True. Par défaut False.
        """
        self.account_list = account_list
        self.debug = debug

    def _debug(self, message: str):
        """
        Affiche un message de débogage si le mode debug est activé.

        Args:
            message (str): Le message à afficher.
        """
        if self.debug:
            print(f"[DEBUG] {message}")

    @lru_cache(maxsize=None)
    def _get_pdf_text(self, file):
        """Cache et retourne le texte du PDF."""
        return file.convert(pdf_to_text)

    def identify(self, file) -> bool:
        """
        Identifie si le fichier est un relevé American Express.

        Args:
            file: Le fichier à identifier.

        Returns:
            bool: True si le fichier est un relevé American Express, False sinon.
        """
        if file.mimetype() != "application/pdf":
            return False
        return "Carte Air France KLM" in self._get_pdf_text(file)

    def file_name(self, _) -> str:
        """
        Retourne le nom du fichier pour le relevé.

        Args:
            _: Paramètre non utilisé, présent pour la compatibilité avec l'interface.

        Returns:
            str: Le nom du fichier standardisé pour les relevés Amex.
        """
        return "Amex.pdf"

    def file_account(self, file) -> Optional[str]:
        """
        Extrait le compte associé au fichier.

        Args:
            file: Le fichier à analyser.

        Returns:
            Optional[str]: Le nom du compte associé ou None si non trouvé.
        """
        text = self._get_pdf_text(file)
        match = re.search(self.ACCOUNT_NUMBER_PATTERN, text)
        if not match:
            self._handle_parsing_error(
                "Numéro de compte non trouvé dans le relevé"
            )
        return self.account_list.get(match.group(1)) if match else None

    def file_date(self, file):
        """
        Extrait la date du relevé.

        Args:
            file: Le fichier à analyser.

        Returns:
            date: La date du relevé ou None si non trouvée.
        """
        text = self._get_pdf_text(file)
        match = re.search(self.STATEMENT_DATE_PATTERN, text)
        return (
            parse_datetime(match.group(1), dayfirst=True).date()
            if match
            else None
        )

    def extract(self, file, existing_entries=None) -> List[data.Directive]:
        """
        Extrait les transactions et le solde du relevé.

        Cette méthode analyse le contenu du fichier PDF, extrait les transactions
        et le solde, puis les convertit en directives Beancount.

        Args:
            file: Le fichier à analyser.
            existing_entries: Les entrées existantes (non utilisé).

        Returns:
            List[data.Directive]: Liste des directives extraites (transactions et solde).
        """
        text = self._get_pdf_text(file)
        self._debug(f"Contenu du PDF :\n{text}")

        statement_date = self._extract_statement_date(text)
        account_number = self._extract_account_number(text)
        transactions = self._extract_transactions(text, statement_date)
        balance = self._extract_balance(text, account_number)

        return [
            self._create_transaction(t, account_number, file)
            for t in transactions
        ] + [balance]

    def _extract_statement_date(self, text: str) -> Dict[str, str]:
        """
        Extrait la date du relevé à partir du texte fourni.

        Cette méthode recherche la date du relevé dans le texte en utilisant
        le motif défini dans STATEMENT_DATE_PATTERN. Si une date est trouvée,
        elle est divisée en jour, mois et année.

        Args:
            text (str): Le texte du relevé à analyser.

        Returns:
            Dict[str, str]: Un dictionnaire contenant les parties de la date
                            (clés : 'day', 'month', 'year'). Retourne un
                            dictionnaire vide si aucune date n'est trouvée.
        """
        match = re.search(self.STATEMENT_DATE_PATTERN, text)
        if match:
            date_str = match.group(1)
            date_parts = date_str.split("/")
            if len(date_parts) == 3:
                return {
                    "day": date_parts[0],
                    "month": date_parts[1],
                    "year": date_parts[2],
                }
        return {}

    def _extract_account_number(self, text: str) -> str:
        """
        Extrait le numéro de compte du texte.

        Args:
            text (str): Le texte du relevé.

        Returns:
            str: Le numéro de compte.

        Raises:
            ValueError: Si le numéro de compte n'est pas trouvé dans le texte.
        """
        match = re.search(self.ACCOUNT_NUMBER_PATTERN, text)
        if not match:
            self._handle_parsing_error(
                "Numéro de compte non trouvé dans le relevé"
            )
        return match.group(1)

    def _extract_transactions(
        self, text: str, statement_date: Dict[str, str]
    ) -> List[Dict]:
        """
        Extrait les transactions du texte.

        Cette méthode parcourt le texte du relevé pour identifier et extraire
        toutes les transactions individuelles.

        Args:
            text (str): Le texte du relevé.
            statement_date (Dict[str, str]): La date du relevé.

        Returns:
            List[Dict]: Liste des transactions extraites, chacune représentée par un dictionnaire.
        """
        transactions = []
        chunks = re.findall(self.TRANSACTION_PATTERN, text)

        for chunk in chunks:
            transaction = self._parse_transaction(chunk, statement_date)
            if transaction:
                transactions.append(transaction)

        return transactions

    def _parse_transaction(
        self, chunk: str, statement_date: Dict[str, str]
    ) -> Optional[Dict]:
        """
        Parse une transaction individuelle.

        Cette méthode analyse une ligne de transaction pour en extraire les détails,
        y compris la date, le montant, le bénéficiaire et le type de transaction.

        Args:
            chunk (str): Le texte de la transaction.
            statement_date (Dict[str, str]): La date du relevé.

        Returns:
            Optional[Dict]: Les détails de la transaction ou None si le parsing échoue.
                Le dictionnaire contient les clés suivantes :
                - 'date': La date de la transaction (datetime.datetime)
                - 'amount': Le montant de la transaction (beancount.core.amount.Amount)
                - 'payee': Le bénéficiaire de la transaction (str)
                - 'type': Le type de transaction ('Débit' ou 'Credit')
        """
        date_match = re.search(self.TRANSACTION_DATE_PATTERN, chunk)
        amount_match = re.search(self.TRANSACTION_DETAILS_PATTERN, chunk)

        if not date_match or not amount_match:
            return None

        raw_date = date_match.group(2)
        month = date_match.group(2).split()[1]
        current_year = int(statement_date["year"])
        transaction_year = (
            current_year
            if month != "déc" or statement_date["month"] != "01"
            else current_year - 1
        )

        transaction_date = parse_datetime(
            traduire_mois(f"{raw_date} {transaction_year}")
        )

        # Vérifier si la date de transaction est dans le futur
        if transaction_date > datetime.now():
            transaction_date = transaction_date.replace(
                year=transaction_year - 1
            )

        return {
            "date": transaction_date,
            "amount": self._parse_amount(
                amount_match.group(2), amount_match.group(3)
            ),
            "payee": re.sub(r"\s+", " ", amount_match.group(1)),
            "type": "Débit" if amount_match.group(3) else "Credit",
        }

    def _parse_amount(
        self, amount_str: str, credit_indicator: Optional[str]
    ) -> amount.Amount:
        """
        Parse le montant d'une transaction.

        Cette méthode convertit une chaîne de caractères représentant un montant
        en un objet Amount de Beancount, en tenant compte du signe (débit ou crédit).

        Args:
            amount_str (str): Le montant en chaîne de caractères.
            credit_indicator (Optional[str]): Indicateur de crédit.

        Returns:
            amount.Amount: Le montant parsé sous forme d'objet Amount de Beancount.
        """
        decimal_amount = Decimal(amount_str.replace(",", ".").replace(" ", ""))
        return amount.Amount(
            decimal_amount if credit_indicator else -decimal_amount, "EUR"
        )

    def _extract_balance(self, text: str, account_number: str) -> data.Balance:
        """
        Extrait le solde du relevé.

        Cette méthode recherche et extrait le solde total du relevé, puis crée
        une directive Balance de Beancount correspondante.

        Args:
            text (str): Le texte du relevé.
            account_number (str): Le numéro de compte.

        Returns:
            data.Balance: Le solde extrait sous forme de directive Balance de Beancount.
        """
        match = re.search(self.BALANCE_PATTERN, text)
        balance_amount = (
            -Decimal(match.group(1).replace(",", ".").replace(" ", ""))
            if match
            else Decimal(0)
        )

        date_match = re.search(self.STATEMENT_DATE_PATTERN, text)
        balance_date = (
            parse_datetime(date_match.group(1), dayfirst=True).date()
            + timedelta(1)
            if date_match
            else None
        )

        return data.Balance(
            meta=data.new_metadata("", 0, {"source": "pdfamex"}),
            date=balance_date,
            account=self.account_list[account_number],
            amount=amount.Amount(balance_amount, "EUR"),
            tolerance=None,
            diff_amount=None,
        )

    def _create_transaction(
        self, transaction: Dict, account_number: str, file
    ) -> data.Transaction:
        """
        Crée une transaction Beancount à partir des données extraites.

        Cette méthode convertit les détails d'une transaction extraite en une
        directive Transaction de Beancount.

        Args:
            transaction (Dict): Les détails de la transaction.
            account_number (str): Le numéro de compte.
            file: Le fichier source.

        Returns:
            data.Transaction: La transaction Beancount créée.
        """
        meta = data.new_metadata(
            file.name, 0, {"source": "pdfamex", "type": transaction["type"]}
        )
        posting = data.Posting(
            account=self.account_list[account_number],
            units=transaction["amount"],
            cost=None,
            flag=None,
            meta=None,
            price=None,
        )
        return data.Transaction(
            meta=meta,
            date=transaction["date"].date(),
            flag=flags.FLAG_OKAY,
            payee=transaction["payee"] or "inconnu",
            narration="",
            tags=data.EMPTY_SET,
            links=data.EMPTY_SET,
            postings=[posting],
        )

    def _handle_parsing_error(
        self, message: str, details: Optional[str] = None
    ):
        """
        Gère les erreurs de parsing en les enregistrant et en levant une exception.

        Args:
            message (str): Le message d'erreur principal.
            details (Optional[str]): Détails supplémentaires sur l'erreur.

        Raises:
            ValueError: Avec le message d'erreur formaté.
        """
        error_msg = f"Erreur de parsing : {message}"
        if details:
            error_msg += f"\nDétails : {details}"
        self._debug(error_msg)
        raise ValueError(error_msg)
