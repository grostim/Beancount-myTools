"""Importer pour les relevés PDF de Boursorama.
Cet importateur identifie le fichier à partir de son contenu et ne prend en charge que le classement,
il ne peut pas extraire de transactions à partir de la conversion PDF en texte. Ceci est courant,
et j'ai pensé fournir un exemple de fonctionnement.

De plus, il utilise une bibliothèque externe appelée pdftotext, qui peut ou non être installée sur
votre machine. Cet exemple montre comment écrire un test qui est automatiquement ignoré
lorsqu'un outil externe n'est pas installé.
"""

__copyright__ = "Copyright (C) 2016 Martin Blais / Modifié en 2019 par Grostim"
__license__ = "GNU GPLv2"

import re
import datetime
import logging
import os
from dateutil.parser import parse as parse_datetime
from beancount.core import amount, data, flags, position
import beangulp
try:
    from myutils import pdf_to_text
except ImportError:
    from ..myutils import pdf_to_text
from beancount.core.number import Decimal, D
from decimal import InvalidOperation

class PDFBourso(beangulp.Importer):
    """Un importateur pour les relevés PDF Boursorama."""

    # Déplacer les constantes de classe en haut pour une meilleure lisibilité
    DOCUMENT_TYPES = {
        "DividendeBourse": r"COUPONS REMBOURSEMENTS :",
        "EspeceBourse": r"RELEVE COMPTE ESPECES :",
        "ETR": r"(?:VENTE|ACHAT) COMPTANT[\s0-9]*ETR",
        "ACTION": r"(?:VENTE|ACHAT) COMPTANT[\s0-9]*ACTION",
        "OPCVM": r"OPERATION SUR OPC",
        "CB": r"Relevé de Carte",
        "Compte": r"BOURSORAMA BANQUE|BOUSFRPPXXX|RCS\sNanterre\s351\s?058\s?151",
        "Amortissement": r"tableau d'amortissement|Echéancier Prévisionnel|Échéancier Définitif"
    }

    REGEX_COMPTE_COMPTE = r"\s*(\d{11})"
    REGEX_COMPTE_CB = r"\s*((4979|4810)\*{8}\d{4})"
    REGEX_COMPTE_AMORTISSEMENT = r"N(?:°|º) du crédit\s*:\s?(\d{5}\s?-\s?\d{11})"
    REGEX_COMPTE_ESPECE_DIVIDENDE_BOURSE = r"40618\s\d{5}\s(\d{11})\s"
    REGEX_COMPTE_BOURSE_OPCVM = r"\d{5}\s\d{5}\s(\d{11})\s"
    REGEX_ISIN = r"Code ISIN\s:\s*([A-Z,0-9]{12})"

    DATE_REGEX = r"(?:le\s|au\s*|Date départ\s*:\s)(\d*\/\d*\/\d*)"

    REGEX_SOLDE_INITIAL = r"SOLDE\s(?:EN\sEUR\s+)?AU\s:(\s+)(\d{1,2}\/\d{2}\/\d{4})(\s+)((?:\d{1,3}\.)?\d{1,3},\d{2})"
    REGEX_OPERATION_COMPTE = r"\d{1,2}\/\d{2}\/\d{4}\s(.*)\s(\d{1,2}\/\d{2}\/\d{4})\s(\s*)\s((?:\d{1,3}\.)?\d{1,3},\d{2})(?:(?:\n.\s{8,20})(.+?))?\n"
    REGEX_SOLDE_FINAL = r"Nouveau solde en EUR :(\s+)((?:\d{1,3}\.)?(?:\d{1,3}\.)?\d{1,3},\d{2})"
    REGEX_DATE_SOLDE_FINAL = r"(\d{1,2}\/\d{2}\/\d{4}).*40618"
    REGEX_AMOUNT = r"((?:\d{1,3}\.)?(?:\d{1,3}\.)?\d{1,3},\d{2})"

    REGEX_AMORTISSEMENT_OPERATION = r"(\d*/\d*/\d*)\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})"

    REGEX_CB_OPERATION = r"(\d{1,2}\/\d{2}\/\d{4})\s*(CARTE|CION OP\.ETR)\s(.*)\s((?:\d{1,3}\.)?\d{1,3},\d{2})"
    REGEX_CB_SOLDE_FINAL = r"A VOTRE DEBIT LE\s(\d{1,2}\/\d{2}\/\d{4})\s*((?:\d{1,3}\.)?(?:\d{1,3}\.)?\d{1,3},\d{2})"

    REGEX_ETR_MONTANT = r"Montant transaction\s*Montant transaction brut\s*Intérêts\s*total brut\s*Courtages\s*Montant transaction net\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*"
    REGEX_BOURSE_FRAIS = r"Commission\s*Frais divers\s*Montant total des frais\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*"
    REGEX_BOURSE_DETAILS = r"locale d'exécution\s*Quantité\s*Informations sur la valeur\s*Informations sur l'exécution\s*(\d{1,2}\/\d{2}\/\d{4})\s*(\d{0,3}\s\d{1,3})\s*([\s\S]{0,20})?\s*"
    REGEX_BOURSE_COURS = r"Cours exécuté :\s*(\d{0,3}\s\d{1,3}[,.]?\d{0,4})\s([A-Z]{1,3})"
    REGEX_BOURSE_ACHAT = r"ACHAT COMPTANT"

    REGEX_ACTION_MONTANT = r"Montant brut\s*Commission\s*Frais\s\(.\)\s*Montant net au crédit de votre compte\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(?:(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3}))?\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*"

    REGEX_OPCVM_MONTANT = r"Montant brut\s*Droits d'entrée\s*Frais H.T.\s*T.V.A.\s*Montant net au débit de votre compte\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s"
    REGEX_OPCVM_DETAILS = r"(\d{1,2}\/\d{2}\/\d{4})\s*(\d{0,3}\s\d{1,3}[.,]?\d{0,4})\s*([\s\S]{0,20})?\s*"
    REGEX_OPCVM_COURS = r"Valeur liquidative :\s*(\d{0,3}\s\d{1,3}[,.]\d{0,4})\s([A-Z]{1,3})"
    REGEX_OPCVM_SOUSCRIPTION = r"SOUSCRIPTION"

    REGEX_DIVIDENDE_DETAILS = r"(\d{2}\/\d{2}\/\d{4})\s*(\d{1,5})\s*(.*)\s\(([A-Z]{2}[A-Z,0-9]{10})\)\s*(\d{0,3}\s\d{1,3}[,.]\d{2})\s*(\d{0,3}\s\d{1,3}[,.]\d{2})?\s*(\d{0,3}\s\d{1,3}[,.]\d{2})\s*(\d{0,3}\s\d{1,3}[,.]\d{2})\s*(\d{0,3}\s\d{1,3}[,.]\d{2})"

    REGEX_ESPECE_BOURSE_SOLDE = r"(\d*/\d*/\d*).*SOLDE\s*(\d{0,3}\s\d{1,3}[,.]\d{1,3})"

    def __init__(self, accountList, debug: bool = False):
        """
        Initialise l'importateur PDFBourso.

        :param accountList: Un dictionnaire de comptes
        :type accountList: dict
        :param debug: Active le mode débogage si True, par défaut False
        :type debug: bool
        """
        assert isinstance(accountList, dict), "La liste de comptes doit être de type dict"
        self.accountList = accountList
        self.debug = debug
        self.logger = logging.getLogger(__name__)
        if debug:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

    def _debug(self, message: str):
        self.logger.debug(message)

    def _error(self, message: str):
        self.logger.error(message)

    def identify(self, file):
        try:
            if not file.lower().endswith(".pdf"):
                return False

            text = pdf_to_text(file)
            
            for doc_type, regex in self.DOCUMENT_TYPES.items():
                if re.search(regex, text):
                    self.type = doc_type
                    return True
            
            return False
        except Exception as e:
            self._error(f"Erreur lors de l'identification du fichier : {str(e)}")
            return False

    def filename(self, file):
        """
        Retourne un nom de fichier normalisé basé sur le type de relevé.

        :param file: Le fichier à traiter
        :type file: object
        :return: Le nom de fichier normalisé
        :rtype: str
        """
        self.identify(file)
        if self.type == "DividendeBourse":
            return "Relevé Dividendes.pdf"
        elif self.type == "EspeceBourse":
            return "Relevé Espece.pdf"
        elif self.type in["ETR","OPCVM","ACTION"]:
            return "Relevé Operation.pdf"
        elif self.type == "Compte":
            return "Relevé Compte.pdf"
        elif self.type == "CB":
            return "Relevé CB.pdf"
        else:
            return "Boursorama.pdf"

    def account(self, file):
        """
        Extrait et retourne le numéro de compte associé au fichier.

        :param file: Le fichier à traiter
        :type file: object
        :return: Le numéro de compte ou l'identifiant du compte
        :rtype: str
        """
        # Recherche du numéro de compte dans le fichier.
        text = pdf_to_text(file)
        self.identify(file)
        
        if self.type == "Compte":
            control = self.REGEX_COMPTE_COMPTE
        elif self.type == "CB":
            control = self.REGEX_COMPTE_CB
        elif self.type == "Amortissement":
            control = self.REGEX_COMPTE_AMORTISSEMENT
        elif self.type in ["EspeceBourse", "DividendeBourse"]:
            control = self.REGEX_COMPTE_ESPECE_DIVIDENDE_BOURSE
        elif self.type in ["ETR", "OPCVM", "ACTION"]:
            control = self.REGEX_COMPTE_BOURSE_OPCVM
        

        match = re.search(control, text)
        
        if match:
            self._debug(f"Numéro de compte extrait : {match.group(1)}")
            compte = match.group(1)
            if self.type in ["ETR", "OPCVM", "ACTION"]:
                match_isin = re.search(self.REGEX_ISIN, text)
                if match_isin:
                    isin = match_isin.group(1)
                    self._debug(f"Compte et ISIN : {self.accountList[compte]}:{isin}")
                    return f"{self.accountList[compte]}:{isin}"
            elif self.type in ["DividendeBourse", "EspeceDividende"]:
                return f"{self.accountList[compte]}:Cash"
            else:
                return self.accountList[compte]

    def date(self, file):
        """
        Extrait et retourne la date du relevé.

        :param file: Le fichier à traiter
        :type file: object
        :return: La date du relevé
        :rtype: datetime.date
        """
        text = pdf_to_text(file)
        match = re.search(self.DATE_REGEX, text)
        if match:
            return parse_datetime(match.group(1), dayfirst=True).date()
        

    def _parse_decimal(self, value: str) -> Decimal:
        try:
            cleaned = value.replace(" ", "").replace("\xa0", "").replace(r"\u00a", "")
            # Remove thousands separators (e.g., "1.328,93")
            cleaned = cleaned.replace(".", "")
            # Convert decimal comma to dot
            cleaned = cleaned.replace(",", ".")
            return Decimal(cleaned)
        except InvalidOperation:
            self._error(f"Impossible de convertir '{value}' en Decimal")
            return Decimal('0')

    def _find_compte_columns(self, text: str):
        for line in text.splitlines():
            if "Débit" not in line or "Crédit" not in line:
                continue
            if "Libell" not in line and "Date opération" not in line:
                continue
            try:
                columns = {
                    "debit": line.index("Débit"),
                    "credit": line.index("Crédit"),
                }
                self._debug(f"Colonnes détectées : {columns}")
                return columns
            except ValueError:
                continue
        self._debug("Colonnes Débit/Crédit introuvables, repli sur l'heuristique historique")
        return None

    def _column_from_offset(self, text: str, offset: int) -> int:
        line_start = text.rfind("\n", 0, offset) + 1
        return offset - line_start

    def _sign_from_column(self, column: int, columns, fallback_sign: int) -> int:
        if columns:
            credit_col = columns.get("credit")
            debit_col = columns.get("debit")
            if credit_col is not None and column >= credit_col:
                return 1
            if debit_col is not None and column >= debit_col:
                return -1
        return fallback_sign

    def _signed_decimal_from_match(self, text: str, match, group_index: int, columns, fallback_sign: int) -> Decimal:
        value = self._parse_decimal(match.group(group_index))
        column = self._column_from_offset(text, match.start(group_index))
        sign = self._sign_from_column(column, columns, fallback_sign)
        return value if sign > 0 else -value

    def _find_final_balance_amount(self, text: str):
        offset = 0
        for raw_line in text.splitlines(keepends=True):
            line = raw_line.rstrip("\n")
            if "Nouveau solde en EUR" not in line:
                offset += len(raw_line)
                continue
            matches = list(re.finditer(self.REGEX_AMOUNT, line))
            if matches:
                match = matches[-1]
                return match.group(1), offset + match.start(1)
            offset += len(raw_line)
        return None

    def _final_balance_date(self, file, text: str):
        match = re.search(self.REGEX_DATE_SOLDE_FINAL, text)
        if match:
            return parse_datetime(match.group(1), dayfirst=True).date()
        return self.date(file)

    def extract(self, file, existing=None, **kwargs):
        try:
            document = f"{self.date(file)} {self.filename(file)}"
            text = pdf_to_text(file)
            #self._debug(f"Contenu du PDF :\n{text}")

            entries = []

            self._debug(f"Type de document : {self.type}")

            extract_methods = {
                "DividendeBourse": self._extract_dividende_bourse,
                "EspeceBourse": self._extract_espece_bourse,
                "ACTION": self._extract_action,
                "ETR": self._extract_etr,
                "OPCVM": self._extract_opcvm,
                "Compte": self._extract_compte,
                "Amortissement": self._extract_amortissement,
                "CB": self._extract_cb
            }

            extract_method = extract_methods.get(self.type)
            if extract_method:
                entries.extend(extract_method(file, text, document))
                self._debug(f"Execution de la methode: {extract_method}")
            else:
                self._error(f"Méthode d'extraction non trouvée pour le type : {self.type}")

            cleaned = []
            for e in entries:
                if hasattr(e, "date") and isinstance(getattr(e, "date"), str):
                    try:
                        e = e._replace(date=parse_datetime(e.date).date())
                    except Exception:
                        pass
                cleaned.append(e)
            return cleaned
        except Exception as e:
            self._error(f"Erreur lors de l'extraction des données : {str(e)}")
            return []

    def _extract_dividende_bourse(self, file, text, document):
        try:
            entries = []
            compte = self.account(file)
            control = self.REGEX_DIVIDENDE_DETAILS
            chunks = re.findall(control, text)
            meta = data.new_metadata(file, 0)
            meta["source"] = "pdfbourso"
            meta["document"] = document
            
            for chunk in chunks:
                try:
                    postings = [
                        self._create_posting("Revenus:Dividendes", self._parse_decimal(chunk[4]) * -1, "EUR"),
                        self._create_posting("Depenses:Impots:IR", self._parse_decimal(chunk[5] or '0') + self._parse_decimal(chunk[6]), "EUR"),
                        self._create_posting(compte, self._parse_decimal(chunk[7]), "EUR")
                    ]
                    
                    transaction = self._create_transaction(
                        meta,
                        parse_datetime(chunk[0], dayfirst=True).date(),
                        f"Dividende pour {chunk[1]} titres {chunk[2]}",
                        None,
                        {chunk[3]},
                        postings
                    )
                    entries.append(transaction)
                except Exception as e:
                    self._error(f"Erreur lors du traitement d'un dividende : {str(e)}")
            
            return entries
        except Exception as e:
            self._error(f"Erreur lors de l'extraction des dividendes : {str(e)}")
            return []

    def _extract_espece_bourse(self, file, text, document):
        """
        Extrait les données pour les espèces en bourse.

        :param file: Le fichier à traiter
        :type file: object
        :param text: Le contenu texte du fichier
        :type text: str
        :param document: L'identifiant du document
        :type document: str
        :return: Une liste d'entrées extraites
        :rtype: list
        """
        entries = []
        print(self.account(file))
        control = self.REGEX_ESPECE_BOURSE_SOLDE
        chunks = re.findall(control, text)
        meta = data.new_metadata(file, 0)
        meta["source"] = "pdfbourso"
        meta["document"] = document
        
        for chunk in chunks:
            print(chunk[0])
            print(chunk[1])
            balance = data.Balance(
                meta,
                parse_datetime(chunk[0], dayfirst=True).date(),
                self.account(file) + ":Cash", # type: ignore
                amount.Amount(self._parse_decimal(chunk[1]), "EUR"),
                None,
                None,
            )
            entries.append(balance)
        
        return entries

    def _extract_action(self, file, text, document):
        """
        Extrait les données pour les opérations boursières.

        :param file: Le fichier à traiter
        :type file: object
        :param text: Le contenu texte du fichier
        :type text: str
        :param document: L'identifiant du document
        :type document: str
        :return: Une liste d'entrées extraites
        :rtype: list
        """
        entries = []
        # Identification du numéro de compte
        control = self.REGEX_COMPTE_BOURSE_OPCVM
        match = re.search(control, text)
        if match:
            compte = match.group(1)

        # Si débogage, affichage de l'extraction
        self._debug(f"Numéro de compte extrait : {compte}")

        ope = dict()

        match = re.search(self.REGEX_ACTION_MONTANT, text)
        if match:
            ope["Montant Total"] = match.group(7)
            ope["currency Total"] = match.group(8)
            ope["Montant TTF"] = match.group(5) or "0.0"
            ope["currency TTF"] = match.group(6)
            ope["Montant Frais"] = match.group(3)
            ope["currency Frais"] = match.group(4)
        else:
            self.logger.info("Montant introuvable")
        self._debug(f"Montant Total : {ope['Montant Total']}")
        self._debug(f"Devise Total : {ope['currency Total']}")
        self._debug(f"Frais : {ope['Montant Frais']}")
        self._debug(f"TTF : {ope['Montant TTF']}")
        self._debug(f"Devise Frais : {ope['currency Frais']}")

        match = re.search(self.REGEX_ISIN, text)
        if match:
            ope["ISIN"] = match.group(1)
        else:
            self.logger.info("ISIN introuvable")

        match = re.search(self.REGEX_BOURSE_DETAILS, text)
        if match:
            ope["Date"] = match.group(1)
            ope["Quantité"] = match.group(2)
            ope["Designation"] = match.group(3)
        else:
            self.logger.info("Date, Qté, Designation introuvable")

        match = re.search(self.REGEX_BOURSE_COURS, text)
        if match:
            ope["Cours"] = match.group(1)
            ope["currency Cours"] = match.group(2)
        else:
            self.logger.info("Cours introuvable")
        self._debug(f"Date de l'opération : {ope['Date']}")

        match = re.search(self.REGEX_BOURSE_ACHAT, text)
        if match:
            ope["Achat"] = True
        else:
            ope["Achat"] = False

        # Creation de la transaction
        postings = [
            self._create_posting(
                self.accountList[compte] + ":" + ope["ISIN"],
                self._parse_decimal(ope["Quantité"]) * (1 if ope["Achat"] else -1),
                ope["ISIN"],
                cost=position.Cost(
                    self._parse_decimal(ope["Cours"]),
                    ope["currency Cours"],
                    parse_datetime(ope["Date"], dayfirst=True).date(),
                    None,
                ) if ope["Achat"] else None,
                price=amount.Amount(
                    self._parse_decimal(ope["Cours"]),
                    ope["currency Cours"],
                ),
            ),
            self._create_posting(
                self.accountList[compte] + ":Cash",
                self._parse_decimal(ope["Montant Total"]) * (-1 if ope["Achat"] else 1),
                ope["currency Total"],
            ),
            self._create_posting(
                "Depenses:Banque:Frais",
                self._parse_decimal(ope["Montant Frais"]) + self._parse_decimal(ope["Montant TTF"]),
                ope["currency Frais"],
            ),
        ]

        meta = data.new_metadata(file, 0)
        meta["source"] = "pdfbourso"
        meta["document"] = document

        transaction = self._create_transaction(
            meta,
            parse_datetime(ope["Date"], dayfirst=True).date(),
            ope["Designation"] or "inconnu",
            ope["ISIN"],
            {ope["ISIN"]},
            postings,
        )
        entries.append(transaction)

        return entries

    def _extract_etr(self, file, text, document):
        """
        Extrait les données pour les opérations boursières.

        :param file: Le fichier à traiter
        :type file: object
        :param text: Le contenu texte du fichier
        :type text: str
        :param document: L'identifiant du document
        :type document: str
        :return: Une liste d'entrées extraites
        :rtype: list
        """
        entries = []
        # Identification du numéro de compte
        control = self.REGEX_COMPTE_BOURSE_OPCVM
        match = re.search(control, text)
        if match:
            compte = match.group(1)

        # Si débogage, affichage de l'extraction
        self._debug(f"Numéro de compte extrait : {compte}")

        ope = dict()

        match = re.search(self.REGEX_ETR_MONTANT, text)
        if match:
            ope["Montant Total"] = match.group(5)
            ope["currency Total"] = match.group(6)
        else:
            self.logger.info("Montant introuvable")
        self._debug(f"Montant Total : {ope['Montant Total']}")
        self._debug(f"Devise Total : {ope['currency Total']}")

        match = re.search(self.REGEX_BOURSE_FRAIS, text)
        if match:
            ope["Frais"] = match.group(5)
            ope["currency Frais"] = match.group(6)
        else:
            self.logger.info("Frais introuvable")

        match = re.search(self.REGEX_ISIN, text)
        if match:
            ope["ISIN"] = match.group(1)
        else:
            self.logger.info("ISIN introuvable")

        match = re.search(self.REGEX_BOURSE_DETAILS, text)
        if match:
            ope["Date"] = match.group(1)
            ope["Quantité"] = match.group(2)
            ope["Designation"] = match.group(3)
        else:
            self.logger.info("Date, Qté, Designation introuvable")

        match = re.search(self.REGEX_BOURSE_COURS, text)
        if match:
            ope["Cours"] = match.group(1)
            ope["currency Cours"] = match.group(2)
        else:
            self.logger.info("Cours introuvable")
        self._debug(f"Date de l'opération : {ope['Date']}")

        match = re.search(self.REGEX_BOURSE_ACHAT, text)
        if match:
            ope["Achat"] = True
        else:
            ope["Achat"] = False

        # Creation de la transaction
        postings = [
            self._create_posting(
                self.accountList[compte] + ":" + ope["ISIN"],
                self._parse_decimal(ope["Quantité"]) * (1 if ope["Achat"] else -1),
                ope["ISIN"],
                cost=position.Cost(
                    self._parse_decimal(ope["Cours"]),
                    ope["currency Cours"],
                    parse_datetime(ope["Date"], dayfirst=True).date(),
                    None,
                ) if ope["Achat"] else None,
                price=amount.Amount(
                    self._parse_decimal(ope["Cours"]),
                    ope["currency Cours"],
                ),
            ),
            self._create_posting(
                self.accountList[compte] + ":Cash",
                self._parse_decimal(ope["Montant Total"]) * (-1 if ope["Achat"] else 1),
                ope["currency Total"],
            ),
            self._create_posting(
                "Depenses:Banque:Frais",
                self._parse_decimal(ope["Frais"]),
                ope["currency Frais"],
            ),
        ]

        meta = data.new_metadata(file, 0)
        meta["source"] = "pdfbourso"
        meta["document"] = document

        transaction = self._create_transaction(
            meta,
            parse_datetime(ope["Date"], dayfirst=True).date(),
            ope["Designation"] or "inconnu",
            ope["ISIN"],
            {ope["ISIN"]},
            postings,
        )
        entries.append(transaction)

        return entries

    def _extract_opcvm(self, file, text, document):
        """
        Extrait les données pour les opérations OPCVM.

        :param file: Le fichier à traiter
        :type file: object
        :param text: Le contenu texte du fichier
        :type text: str
        :param document: L'identifiant du document
        :type document: str
        :return: Une liste d'entrées extraites
        :rtype: list
        """
        entries = []
        # Identification du numéro de compte
        control = self.REGEX_COMPTE_BOURSE_OPCVM
        match = re.search(control, text)
        if match:
            compte = match.group(1)

        # Si débogage, affichage de l'extraction
        self._debug(f"Numéro de compte extrait : {compte}")

        ope = dict()

        match = re.search(self.REGEX_OPCVM_MONTANT, text)
        if match:
            ope["Montant Total"] = match.group(7)
            ope["currency Total"] = match.group(8)
            ope["Frais"] = match.group(5)
            ope["currency Frais"] = match.group(6)
            ope["Droits"] = match.group(3)
            ope["currency Droits"] = match.group(4)
        else:
            self.logger.info("Montant introuvable")
        self._debug(f"Montant Total : {ope['Montant Total']}")
        self._debug(f"Devise Total : {ope['currency Total']}")

        match = re.search(self.REGEX_ISIN, text)
        if match:
            ope["ISIN"] = match.group(1)
        else:
            self.logger.info("ISIN introuvable")

        match = re.search(self.REGEX_OPCVM_DETAILS, text)
        if match:
            ope["Date"] = match.group(1)
            ope["Quantité"] = match.group(2)
            ope["Designation"] = match.group(3)
        else:
            self.logger.info("Date, Qté, Designation introuvable")

        match = re.search(self.REGEX_OPCVM_COURS, text)
        if match:
            ope["Cours"] = match.group(1)
            ope["currency Cours"] = match.group(2)
        else:
            self.logger.info("Cours introuvable")
        self._debug(f"Cours : {ope['Cours']}")

        match = re.search(self.REGEX_OPCVM_SOUSCRIPTION, text)
        if match:
            ope["Achat"] = True
        else:
            ope["Achat"] = False

        # Creation de la transaction
        postings = [
            self._create_posting(
                self.accountList[compte] + ":" + ope["ISIN"],
                self._parse_decimal(ope["Quantité"]) * (1 if ope["Achat"] else -1),
                ope["ISIN"],
                cost=position.Cost(
                    self._parse_decimal(ope["Cours"]),
                    ope["currency Cours"],
                    parse_datetime(ope["Date"], dayfirst=True).date(),
                    None,
                ) if ope["Achat"] else None,
                price=amount.Amount(
                    self._parse_decimal(ope["Cours"]),
                    ope["currency Cours"],
                ),
            ),
            self._create_posting(
                self.accountList[compte] + ":Cash",
                self._parse_decimal(ope["Montant Total"]) * (-1 if ope["Achat"] else 1),
                ope["currency Total"],
            ),
            self._create_posting(
                "Depenses:Banque:Frais",
                self._parse_decimal(ope["Frais"]) + self._parse_decimal(ope["Droits"]),
                ope["currency Frais"],
            ),
        ]

        meta = data.new_metadata(file, 0)
        meta["source"] = "pdfbourso"
        meta["document"] = document

        transaction = self._create_transaction(
            meta,
            parse_datetime(ope["Date"], dayfirst=True).date(),
            ope["Designation"] or "inconnu",
            ope["ISIN"],
            {ope["ISIN"]},
            postings,
        )
        entries.append(transaction)

        return entries

    def _extract_compte(self, file, text, document):
        """
        Extrait les données pour les opérations de compte.

        :param file: Le fichier à traiter
        :type file: object
        :param text: Le contenu texte du fichier
        :type text: str
        :param document: L'identifiant du document
        :type document: str
        :return: Une liste d'entrées extraites
        :rtype: list
        """
        entries = []
        # Identification du numéro de compte
        control = self.REGEX_COMPTE_COMPTE
        match = re.search(control, text)
        if match:
            compte = match.group(0).split(" ")[-1]

        # Si debogage, affichage de l'extraction
        self._debug(f"Numéro de compte extrait : {compte}")
        columns = self._find_compte_columns(text)

        # Affichage du solde initial
        match = re.search(self.REGEX_SOLDE_INITIAL, text)
        if match:
            datebalance = parse_datetime(
                match.group(2), dayfirst=True
            ).date() + datetime.timedelta(days=1)
            fallback_length = (
                len(match.group(1))
                + len(match.group(3))
                + len(match.group(2))
                + len(match.group(4))
            )
            fallback_sign = -1 if fallback_length < 84 else 1
            balance = self._signed_decimal_from_match(text, match, 4, columns, fallback_sign)

            meta = data.new_metadata(file, 0)
            meta["source"] = "pdfbourso"
            meta["document"] = document

            entries.append(
                data.Balance(
                    meta,
                    datebalance,
                    self.accountList[compte],
                    amount.Amount(balance, "EUR"),
                    None,
                    None,
                ) # type: ignore
            )

        chunks = list(re.finditer(self.REGEX_OPERATION_COMPTE, text))

        # Si debogage, affichage de l'extraction
        self._debug(f"Chunks extraits : {chunks}")

        index = 0
        for chunk_match in chunks:
            index += 1
            meta = data.new_metadata(file, index)
            meta["source"] = "pdfbourso"
            meta["document"] = document
            ope = dict()
            chunk = chunk_match.groups()

            # Si debogage, affichage de l'extraction
            self._debug(f"Chunk extrait : {chunk}")

            ope["date"] = chunk[1]
            # Si debogage, affichage de l'extraction
            self._debug(f"Date de l'opération : {ope['date']}")

            fallback_length = (
                len(chunk[0])
                + len(chunk[1])
                + len(chunk[2])
                + len(chunk[3])
            )
            fallback_sign = 1 if fallback_length > 148 else -1
            ope["montant"] = self._signed_decimal_from_match(text, chunk_match, 4, columns, fallback_sign)
            ope["type"] = "Credit" if ope["montant"] > 0 else "Debit"
            # Si débogage, affichage de l'extraction
            self._debug(f"Montant de l'opération : {ope['montant']}")

            ope["payee"] = re.sub(r"\s+", " ", chunk[0])
            # Si debogage, affichage de l'extraction
            self._debug(f"Payee : {ope['payee']}")

            ope["narration"] = re.sub(r"\s+", " ", chunk[4] or "")
            # Si debogage, affichage de l'extraction
            self._debug(f"Narration : {ope['narration']}")

            # Creation de la transaction
            postings = [
                self._create_posting(
                    self.accountList[compte],
                    ope["montant"],
                    "EUR",
                ),
            ]
            transaction = self._create_transaction(
                meta,
                parse_datetime(ope["date"], dayfirst=True).date(),
                ope["payee"] or "inconnu",
                ope["narration"],
                data.EMPTY_SET,
                postings,
            )
            entries.append(transaction)

        # Recherche du solde final
        match = re.search(self.REGEX_SOLDE_FINAL, text)
        if match:
            fallback_sign = -1 if len(match.group(1)) < 84 else 1
            balance = self._signed_decimal_from_match(text, match, 2, columns, fallback_sign)
        else:
            final_balance = self._find_final_balance_amount(text)
            balance = None
            if final_balance:
                raw_balance, offset = final_balance
                column = self._column_from_offset(text, offset)
                balance_value = self._parse_decimal(raw_balance)
                sign = self._sign_from_column(column, columns, 1)
                balance = balance_value if sign > 0 else -balance_value

        if balance is not None:
            datebalance = self._final_balance_date(file, text)
            if datebalance:
                self.logger.debug(f"Date balance : {datebalance}")
                meta = data.new_metadata(file, 0)
                meta["source"] = "pdfbourso"
                meta["document"] = document

                entries.append(
                    data.Balance(
                        meta,
                        datebalance,
                        self.accountList[compte],
                        amount.Amount(balance, "EUR"),
                        None,
                        None,
                    ) # type: ignore
                )

        return entries

    def _extract_amortissement(self, file, text, document):
        """
        Extrait les données pour les opérations d'amortissement.

        :param file: Le fichier à traiter
        :type file: object
        :param text: Le contenu texte du fichier
        :type text: str
        :param document: L'identifiant du document
        :type document: str
        :return: Une liste d'entrées extraites
        :rtype: list
        """
        entries = []
        # Identification du numéro de compte
        match = re.search(self.REGEX_COMPTE_AMORTISSEMENT, text)
        if match:
            compte = match.group(1)

        # Si debogage, affichage de l'extraction
        self._debug(f"Numéro de compte : {compte}")

        chunks = re.findall(self.REGEX_AMORTISSEMENT_OPERATION, text)

        # Si debogage, affichage de l'extraction
        self._debug(f"Chunks : {chunks}")

        index = 0
        for chunk in chunks:
            index += 1
            meta = data.new_metadata(file, index)
            meta["source"] = "pdfbourso"
            ope = dict()
            ope["date"] = parse_datetime(chunk[0], dayfirst=True).date()
            ope["prelevement"] = amount.Amount(
                self._parse_decimal(chunk[1]) * -1, "EUR"
            )
            ope["amortissement"] = amount.Amount(
                self._parse_decimal(chunk[2]), "EUR"
            )
            ope["interet"] = amount.Amount(
                self._parse_decimal(chunk[3]), "EUR"
            )
            ope["assurance"] = amount.Amount(
                self._parse_decimal(chunk[4]), "EUR"
            )
            ope["CRD"] = amount.Amount(
                self._parse_decimal(chunk[7])*-1, "EUR"
            )

            # Creation de la transaction
            postings = [
                self._create_posting("Actif:Boursorama:CCJoint", ope["prelevement"].number, "EUR"),
                self._create_posting(self.accountList[compte], ope["amortissement"].number, "EUR"),
                self._create_posting("Depenses:Banque:Interet", ope["interet"].number, "EUR"),
                self._create_posting("Depenses:Banque:AssuEmprunt", ope["assurance"].number, "EUR"),
            ]
            transaction = self._create_transaction(
                meta,
                ope["date"],
                "ECH PRET:8028000060686223",
                "",
                data.EMPTY_SET,
                postings,
            )
            entries.append(transaction)
            entries.append(
                data.Balance(
                    meta,
                    ope["date"] + datetime.timedelta(1),
                    self.accountList[compte],
                    ope["CRD"],
                    None,
                    None,
                ) # type: ignore
            )

        return entries

    def _extract_cb(self, file, text, document):
        """
        Extrait les données pour les opérations CB.

        :param file: Le fichier à traiter
        :type file: object
        :param text: Le contenu texte du fichier
        :type text: str
        :param document: L'identifiant du document
        :type document: str
        :return: Une liste d'entrées extraites
        :rtype: list
        """
        entries = []
        # Identification du numéro de compte
        match = re.search(self.REGEX_COMPTE_CB, text)
        if match:
            compte = match.group(1)

        # Si debogage, affichage de l'extraction
        self._debug(f"Numéro de compte : {compte}")

        chunks = re.findall(self.REGEX_CB_OPERATION, text)

        # Si debogage, affichage de l'extraction
        self._debug(f"Expression régulière utilisée : {self.REGEX_CB_OPERATION}")
        self._debug(f"Chunks extraits : {chunks}")

        index = 0
        for chunk in chunks:
            index += 1
            meta = data.new_metadata(file, index)
            meta["source"] = "pdfbourso"
            meta["document"] = document
            ope = dict()

            # Si debogage, affichage de l'extraction
            self._debug(f"Chunk extrait : {chunk}")

            ope["date"] = chunk[0]
            # Si debogage, affichage de l'extraction
            self._debug(f"Date de l'opération : {ope['date']}")

            ope["type"] = chunk[1]
            # Si debogage, affichage de l'extraction
            self._debug(f"Type d'opération : {ope['type']}")

            ope["montant"] = self._parse_decimal(chunk[3])*-1
            # Si debogage, affichage de l'extraction
            self._debug(f"Montant de l'opération : {ope['montant']}")

            payee = re.sub(r"\s+", " ", chunk[2]).strip()
            if ope["type"] == "CION OP.ETR":
                payee = f"{ope['type']} {payee}".strip()
            ope["payee"] = payee
            # Si debogage, affichage de l'extraction
            self._debug(f"Payee : {ope['payee']}")

            # Creation de la transaction
            postings = [
                self._create_posting(
                    self.accountList[compte],
                    ope["montant"],
                    "EUR",
                ),
            ]
            if ope["type"] == "CION OP.ETR":
                postings.append(
                    self._create_posting(
                        "Depenses:Banque:Frais",
                        -ope["montant"],
                        "EUR",
                    ),
                )
            transaction = self._create_transaction(
                meta,
                parse_datetime(ope["date"], dayfirst=True).date(),
                ope["payee"] or "inconnu",
                None,
                data.EMPTY_SET,
                postings,
            )
            entries.append(transaction)

        # Recherche du solde final
        match = re.search(self.REGEX_CB_SOLDE_FINAL, text)
        if match:
            balance = self._parse_decimal(match.group(2))*-1
            self._debug(f"Balance : {balance}")
            # Recherche de la date du solde final
            match = re.search(self.REGEX_DATE_SOLDE_FINAL, text)
            if match:
                datebalance = parse_datetime(
                    match.group(1), dayfirst=True
                ).date()
                self._debug(f"Date de la balance : {datebalance}")
                meta = data.new_metadata(file, 0)
                meta["source"] = "pdfbourso"
                meta["document"] = document

                entries.append(
                    data.Balance(
                        meta,
                        datebalance,
                        self.accountList[compte],
                        amount.Amount(balance, "EUR"),
                        None,
                        None,
                    ) # type: ignore
                )

        return entries

    def _create_posting(self, account, amount_value, currency, cost=None, price=None):
        """
        Crée un posting pour une transaction.

        :param account: Le compte associé au posting
        :type account: str
        :param amount_value: La valeur du montant
        :type amount_value: Decimal
        :param currency: La devise
        :type currency: str
        :param cost: Le coût, par défaut None
        :type cost: Cost, optional
        :param price: Le prix, par défaut None
        :type price: Amount, optional
        :return: Un objet Posting
        :rtype: data.Posting
        """
        return data.Posting(
            account=account,
            units=amount.Amount(amount_value, currency),
            cost=cost,
            flag=None,
            meta=None,
            price=price,
        )

    def _create_transaction(self, meta, date, payee, narration, tags, postings):
        """
        Crée une transaction.

        :param meta: Les métadonnées de la transaction
        :type meta: dict
        :param date: La date de la transaction
        :type date: datetime.date
        :param payee: Le bénéficiaire
        :type payee: str
        :param narration: La description de la transaction
        :type narration: str
        :param tags: Les tags associés à la transaction
        :type tags: set
        :param postings: Les postings de la transaction
        :type postings: list
        :return: Un objet Transaction
        :rtype: data.Transaction
        """
        if isinstance(date, str):
            date = parse_datetime(date).date()

        return data.Transaction(
            meta=meta,
            date=date,
            flag=flags.FLAG_OKAY,
            payee=payee,
            narration=narration,
            tags=tags,
            links=data.EMPTY_SET,
            postings=postings,
        ) # type: ignore
