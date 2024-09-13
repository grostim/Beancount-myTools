"""Importateur pour les relevés PDF d'American Express."""

import re
from datetime import timedelta
from decimal import Decimal
from typing import List, Dict, Optional

from dateutil.parser import parse as parse_datetime
from beancount.core import amount, data, flags
from beancount.ingest import importer
from myTools.myutils import pdf_to_text, traduire_mois

ACCOUNT_NUMBER_PATTERN = r"xxxx-xxxxxx-(\d{5})"
STATEMENT_DATE_PATTERN = r"xxxx-xxxxxx-\d{5}\s*(\d*/\d*/\d*)"
TRANSACTION_PATTERN = r"\d{1,2}\s[a-zéèûôùê]{3,4}\s*\d{1,2}\s[a-zéèûôùê]{3,4}.*\d+,\d{2}(?:\s*CR)?"

class PDFAmex(importer.ImporterProtocol):
    """
    Importateur pour les relevés PDF American Express.

    Cette classe permet d'extraire les transactions et le solde des relevés
    American Express au format PDF et de les convertir en entrées Beancount.
    """

    def __init__(self, account_list: Dict[str, str], debug: bool = False):
        """
        Initialise l'importateur PDFAmex.

        Args:
            account_list (Dict[str, str]): Dictionnaire associant les numéros de compte aux noms de compte.
            debug (bool, optional): Active le mode debug si True. Par défaut False.
        """
        self.account_list = account_list
        self.debug = debug

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
        text = file.convert(pdf_to_text)
        return text and "Carte Air France KLM" in text

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
        text = file.convert(pdf_to_text)
        match = re.search(self.ACCOUNT_NUMBER_PATTERN, text)
        if not match:
            raise ValueError("Numéro de compte non trouvé dans le relevé")
        return self.account_list.get(match.group(0).split(" ")[-1]) if match else None

    def file_date(self, file):
        """
        Extrait la date du relevé.

        Args:
            file: Le fichier à analyser.

        Returns:
            date: La date du relevé ou None si non trouvée.
        """
        text = file.convert(pdf_to_text)
        match = re.search(r"xxxx-xxxxxx-\d{5}\s*(\d*/\d*/\d*)", text)
        return parse_datetime(match.group(1), dayfirst=True).date() if match else None

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
        text = file.convert(pdf_to_text)
        if self.debug:
            print(text)

        statement_date = self._extract_statement_date(text)
        account_number = self._extract_account_number(text)
        transactions = self._extract_transactions(text, statement_date)
        balance = self._extract_balance(text, account_number)

        entries = [self._create_transaction(t, account_number, file) for t in transactions]
        entries.append(balance)

        return entries

    def _extract_statement_date(self, text: str) -> Dict[str, str]:
        """
        Extrait la date du relevé du texte.

        Args:
            text (str): Le texte du relevé.

        Returns:
            Dict[str, str]: Un dictionnaire contenant le mois et l'année du relevé.
        """
        match = re.search(r"xxxx-xxxxxx-\d{5}\s*\d*/(\d*)/(\d*)", text)
        return {"month": match.group(1), "year": match.group(2)} if match else {}

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
            raise ValueError("Numéro de compte non trouvé dans le relevé")
        return match.group(1)

    def _extract_transactions(self, text: str, statement_date: Dict[str, str]) -> List[Dict]:
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

    def _parse_transaction(self, chunk: str, statement_date: Dict[str, str]) -> Optional[Dict]:
        """
        Parse une transaction individuelle.

        Cette méthode analyse une ligne de transaction pour en extraire les détails,
        y compris la date, le montant, le bénéficiaire et le type de transaction.

        Args:
            chunk (str): Le texte de la transaction.
            statement_date (Dict[str, str]): La date du relevé.

        Returns:
            Optional[Dict]: Les détails de la transaction ou None si le parsing échoue.
        """
        date_match = re.search(r"(\d{1,2}\s[a-zéèûôùê]{3,4})\s*(\d{1,2}\s[a-zéèûôùê]{3,4})", chunk)
        amount_match = re.search(r"\d{1,2}\s[a-zéèûôùê]{3,4}\s*\d{1,2}\s[a-zéèûôùê]{3,4}\s+(.*?)\s+(\d{0,3}\s{0,1}\d{1,3},\d{2})(\s*CR)?$", chunk)

        if not date_match or not amount_match:
            return None

        raw_date = date_match.group(2)
        month = date_match.group(2).split()[1]
        year = statement_date['year'] if month != 'déc' or statement_date['month'] != '01' else str(int(statement_date['year']) - 1)
        
        return {
            "date": parse_datetime(traduire_mois(f"{raw_date} 20{year}")),
            "amount": self._parse_amount(amount_match.group(2), amount_match.group(3)),
            "payee": re.sub(r"\s+", " ", amount_match.group(1)),
            "type": "Débit" if amount_match.group(3) else "Credit"
        }

    def _parse_amount(self, amount_str: str, credit_indicator: Optional[str]) -> amount.Amount:
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
        return amount.Amount(decimal_amount if credit_indicator else -decimal_amount, "EUR")

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
        match = re.search(r"Total des dépenses pour\s+(?:.*?)\s+(\d{0,3}\s{0,1}\d{1,3},\d{2})", text)
        balance_amount = -Decimal(match.group(1).replace(",", ".").replace(" ", "")) if match else Decimal(0)

        date_match = re.search(r"xxxx-xxxxxx-\d{5}\s*(\d*/\d*/\d*)", text)
        balance_date = parse_datetime(date_match.group(1), dayfirst=True).date() + timedelta(1) if date_match else None

        return data.Balance(
            meta=data.new_metadata("", 0, {"source": "pdfamex"}),
            date=balance_date,
            account=self.account_list[account_number],
            amount=amount.Amount(balance_amount, "EUR"),
            tolerance=None,
            diff_amount=None
        )

    def _create_transaction(self, transaction: Dict, account_number: str, file) -> data.Transaction:
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
        meta = data.new_metadata(file.name, 0, {"source": "pdfamex", "type": transaction["type"]})
        posting = data.Posting(
            account=self.account_list[account_number],
            units=transaction["amount"],
            cost=None,
            flag=None,
            meta=None,
            price=None
        )
        return data.Transaction(
            meta=meta,
            date=transaction["date"].date(),
            flag=flags.FLAG_OKAY,
            payee=transaction["payee"] or "inconnu",
            narration="",
            tags=data.EMPTY_SET,
            links=data.EMPTY_SET,
            postings=[posting]
        )