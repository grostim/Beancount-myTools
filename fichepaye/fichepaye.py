"""Importer pour fiche de payes personnelle. (Format propre à mon employeur)
Classement des fichiers uniquement. Pas d'import des transactions.
"""
import re
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional
from functools import lru_cache

from dateutil.parser import parse as parse_datetime
from beancount.core import amount, data, flags
from beancount.ingest import importer
from myTools.myutils import pdf_to_text

class FichePaye(importer.ImporterProtocol):
    """
    Un importateur pour mes propres fiches de paie.

    Cette classe permet d'extraire les informations des fiches de paie au format PDF
    et de les convertir en entrées Beancount.

    Attributes:
        EMPLOYER_IDENTIFIER_PATTERN (str): Motif regex pour identifier l'employeur.
        ACCOUNT_NUMBER_PATTERN (str): Motif regex pour extraire le numéro de compte.
        PAYMENT_DATE_PATTERN (str): Motif regex pour extraire la date de paiement.
        NET_BEFORE_TAX_PATTERN (str): Motif regex pour extraire le net avant impôt.
        INCOME_TAX_PATTERN (str): Motif regex pour extraire l'impôt sur le revenu.
        NET_PAY_PATTERN (str): Motif regex pour extraire le net à payer.
    """

    EMPLOYER_IDENTIFIER_PATTERN = r"Sage|DUO_TECNAL"
    ACCOUNT_NUMBER_PATTERN = r"02568047100015"
    PAYMENT_DATE_PATTERN = r"Paiement\sle\s*(\d{2}\/\d{2}\/\d{4})"
    NET_BEFORE_TAX_PATTERN = r"Net à payer avant impôt sur le revenu\s*(\d{0,3}?\s?\d{0,3}[,.]\d{2})"
    INCOME_TAX_PATTERN = r"Impôt sur le revenu prélevé à la source - PAS\s*\d{0,3}?\s?\d{0,3}[,.]\d{2}\s*-\s\d{0,3}[,.]\d{0,4}\s*(\d{0,3}?\s?\d{0,3}[,.]\d{2})"
    NET_PAY_PATTERN = r"Net payé\s*(\d{0,3}?\s?\d{0,3}[,.]\d{2})"

    def __init__(
        self, 
        account_list: Dict[str, str], 
        debug: bool = False,
        compteCourant="Actif:FIXME",
        compteImpot="Depenses:FIXME",
        payee="Salaire",
        ):
        """
        Initialise l'importateur FichePaye.

        Args:
            account_list (Dict[str, str]): Dictionnaire associant les numéros de compte aux noms de compte.
            debug (bool, optional): Active le mode debug si True. Par défaut False.
            compteCourant (str, optional): Compte courant pour les transactions. Par défaut "Actif:FIXME".
            compteImpot (str, optional): Compte pour l'impôt sur le revenu. Par défaut "Depenses:FIXME".
            payee (str, optional): Nom du payeur pour les transactions. Par défaut "Salaire".

        Cette classe permet d'importer et de traiter les fiches de paie au format PDF,
        en extrayant les informations pertinentes et en les convertissant en entrées Beancount.
        """
        self.account_list = account_list
        self.debug = debug
        self.compteCourant = compteCourant
        self.compteImpot = compteImpot
        self.payee = payee

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
        Identifie si le fichier est une fiche de paie valide.

        Args:
            file: Le fichier à identifier.

        Returns:
            bool: True si le fichier est une fiche de paie valide, False sinon.
        """
        if file.mimetype() != "application/pdf":
            return False
        text = self._get_pdf_text(file)
        self._debug(f"Contenu du PDF :\n{text}")
        return bool(re.search(self.EMPLOYER_IDENTIFIER_PATTERN, text))

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
        self._debug(f"Numéro de compte trouvé : {match.group(0) if match else 'Non trouvé'}")
        return self.account_list.get(match.group(0)) if match else None

    def file_name(self, _) -> str:
        """
        Retourne le nom du fichier pour la fiche de paie.

        Args:
            _: Paramètre non utilisé, présent pour la compatibilité avec l'interface.

        Returns:
            str: Le nom du fichier standardisé pour les fiches de paie.
        """
        return "Bulletin_Paye.pdf"

    def file_date(self, file) -> Optional[datetime.date]:
        """
        Extrait la date de paiement de la fiche de paie.

        Args:
            file: Le fichier à analyser.

        Returns:
            Optional[datetime.date]: La date de paiement ou None si non trouvée.
        """
        text = self._get_pdf_text(file)
        match = re.search(self.PAYMENT_DATE_PATTERN, text)
        return parse_datetime(match.group(1), dayfirst=True).date() if match else None

    def extract(self, file, existing_entries=None) -> List[data.Directive]:
        """
        Extrait les informations de la fiche de paie.

        Cette méthode analyse le contenu du fichier PDF, extrait les informations pertinentes,
        puis les convertit en directives Beancount.

        Args:
            file: Le fichier à analyser.
            existing_entries: Les entrées existantes (non utilisé).

        Returns:
            List[data.Directive]: Liste des directives extraites.
        """
        text = self._get_pdf_text(file)
        payment_date = self.file_date(file)
        account = self.file_account(file)

        net_before_tax = self._extract_amount(text, self.NET_BEFORE_TAX_PATTERN, negate=True)
        income_tax = self._extract_amount(text, self.INCOME_TAX_PATTERN)
        net_pay = self._extract_amount(text, self.NET_PAY_PATTERN)

        transaction = self._create_transaction(payment_date, account, net_before_tax, income_tax, net_pay, file)
        return [transaction]

    def _extract_amount(self, text: str, pattern: str, negate: bool = False) -> amount.Amount:
        """
        Extrait un montant du texte en utilisant le motif spécifié.

        Args:
            text (str): Le texte à analyser.
            pattern (str): Le motif regex pour extraire le montant.
            negate (bool): Si True, le montant sera négatif.

        Returns:
            amount.Amount: Le montant extrait.

        Raises:
            ValueError: Si le montant n'est pas trouvé dans le texte.
        """
        match = re.search(pattern, text)
        if not match:
            raise ValueError(f"Montant non trouvé pour le motif : {pattern}")
        
        decimal_amount = Decimal(match.group(1).replace(",", ".").replace(" ", ""))
        if negate:
            decimal_amount = -decimal_amount
        return amount.Amount(decimal_amount, "EUR")

    def _create_transaction(self, date: datetime.date, account: str, net_before_tax: amount.Amount, 
                            income_tax: amount.Amount, net_pay: amount.Amount, file) -> data.Transaction:
        """
        Crée une transaction Beancount à partir des données extraites.

        Args:
            date (datetime.date): La date de la transaction.
            account (str): Le compte principal.
            net_before_tax (amount.Amount): Le montant net avant impôt.
            income_tax (amount.Amount): Le montant de l'impôt sur le revenu.
            net_pay (amount.Amount): Le montant net à payer.
            file: Le fichier source.

        Returns:
            data.Transaction: La transaction Beancount créée.
        """
        meta = data.new_metadata(file.name, 0, {"source": "fichepaye", "document": f"{date} {self.file_name(None)}"})
        
        postings = [
            data.Posting(account=f"{account}:Salaire", units=net_before_tax, cost=None, price=None, flag=None, meta=None),
            data.Posting(account=self.compteImpot, units=income_tax, cost=None, price=None, flag=None, meta=None),
            data.Posting(account=self.compteCourant, units=net_pay, cost=None, price=None, flag=None, meta=None)
        ]

        return data.Transaction(
            meta=meta,
            date=date,
            flag=flags.FLAG_OKAY,
            payee=self.payee,
            narration="VIREMENT-SALAIRE",
            tags=data.EMPTY_SET,
            links=data.EMPTY_SET,
            postings=postings
        )

    def _handle_parsing_error(self, message: str, details: Optional[str] = None):
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
