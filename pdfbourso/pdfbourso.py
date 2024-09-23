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
from dateutil.parser import parse as parse_datetime
from myutils import pdf_to_text
from beancount.core import amount, data, flags, position
from beancount.ingest import importer
from beancount.core.number import Decimal, D

class PDFBourso(importer.ImporterProtocol):
    """Un importateur pour les relevés PDF Boursorama."""

    # Déplacer les constantes de classe en haut pour une meilleure lisibilité
    DOCUMENT_TYPES = {
        "DividendeBourse": r"COUPONS REMBOURSEMENTS :",
        "EspeceBourse": r"RELEVE COMPTE ESPECES :",
        "Bourse": r"OPERATION DE BOURSE",
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

    DATE_REGEX = r"(?:le\s|au\s*|Date départ\s*:\s)(\d*/\d*/\d*)"

    REGEX_SOLDE_INITIAL = r"SOLDE\s(?:EN\sEUR\s+)?AU\s:(\s+)(\d{1,2}\/\d{2}\/\d{4})(\s+)((?:\d{1,3}\.)?\d{1,3},\d{2})"
    REGEX_OPERATION_COMPTE = r"\d{1,2}\/\d{2}\/\d{4}\s(.*)\s(\d{1,2}\/\d{2}\/\d{4})\s(\s*)\s((?:\d{1,3}\.)?\d{1,3},\d{2})(?:(?:\n.\s{8,20})(.+?))?\n"
    REGEX_SOLDE_FINAL = r"Nouveau solde en EUR :(\s+)((?:\d{1,3}\.)?(?:\d{1,3}\.)?\d{1,3},\d{2})"
    REGEX_DATE_SOLDE_FINAL = r"(\d{1,2}\/\d{2}\/\d{4}).*40618"

    REGEX_AMORTISSEMENT_OPERATION = r"(\d*/\d*/\d*)\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})"

    REGEX_CB_OPERATION = r"(\d{1,2}\/\d{2}\/\d{4})\s*CARTE\s(.*)\s((?:\d{1,3}\.)?\d{1,3},\d{2})"
    REGEX_CB_SOLDE_FINAL = r"A VOTRE DEBIT LE\s(\d{1,2}\/\d{2}\/\d{4})\s*((?:\d{1,3}\.)?(?:\d{1,3}\.)?\d{1,3},\d{2})"

    REGEX_BOURSE_MONTANT = r"Montant transaction\s*Montant transaction brut\s*Intérêts\s*total brut\s*Courtages\s*Montant transaction net\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*"
    REGEX_BOURSE_FRAIS = r"Commission\s*Frais divers\s*Montant total des frais\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*"
    REGEX_BOURSE_DETAILS = r"locale d'exécution\s*Quantité\s*Informations sur la valeur\s*Informations sur l'exécution\s*(\d{1,2}\/\d{2}\/\d{4})\s*(\d{0,3}\s\d{1,3})\s*([\s\S]{0,20})?\s*"
    REGEX_BOURSE_COURS = r"Cours exécuté :\s*(\d{0,3}\s\d{1,3}[,.]\d{0,4})\s([A-Z]{1,3})"
    REGEX_BOURSE_ACHAT = r"ACHAT COMPTANT"

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

    def _debug(self, message: str):
        """
        Affiche un message de débogage si le mode debug est activé.

        :param message: Le message à afficher
        :type message: str
        """
        if self.debug:
            print(f"[DEBUG] {message}")

    def identify(self, file):
        """
        Identifie si le fichier est un relevé Boursorama valide.

        :param file: Le fichier à identifier
        :type file: object
        :return: True si le fichier est identifié comme un relevé Boursorama, False sinon
        :rtype: bool
        """
        if file.mimetype() != "application/pdf":
            return False

        text = file.convert(pdf_to_text)
        self._debug(f"Contenu du PDF :\n{text}")
        
        for doc_type, regex in self.DOCUMENT_TYPES.items():
            if re.search(regex, text):
                self.type = doc_type
                return True
        
        return False

    def file_name(self, file):
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
        elif self.type == "Bourse":
            return "Relevé Operation.pdf"
        elif self.type == "Compte":
            return "Relevé Compte.pdf"
        elif self.type == "CB":
            return "Relevé CB.pdf"
        else:
            return "Boursorama.pdf"

    def file_account(self, file):
        """
        Extrait et retourne le numéro de compte associé au fichier.

        :param file: Le fichier à traiter
        :type file: object
        :return: Le numéro de compte ou l'identifiant du compte
        :rtype: str
        """
        # Recherche du numéro de compte dans le fichier.
        text = file.convert(pdf_to_text)
        self.identify(file)
        
        if self.type == "Compte":
            control = self.REGEX_COMPTE_COMPTE
        elif self.type == "CB":
            control = self.REGEX_COMPTE_CB
        elif self.type == "Amortissement":
            control = self.REGEX_COMPTE_AMORTISSEMENT
        elif self.type in ["EspeceBourse", "DividendeBourse"]:
            control = self.REGEX_COMPTE_ESPECE_DIVIDENDE_BOURSE
        elif self.type in ["Bourse", "OPCVM"]:
            control = self.REGEX_COMPTE_BOURSE_OPCVM
        
        # Si debogage, affichage de l'extraction
        self._debug(f"Type de document : {self.type}")
        
        match = re.search(control, text)
        
        if match:
            self._debug(f"Numéro de compte extrait : {match.group(1)}")
            compte = match.group(1)
            if self.type in ["Bourse", "OPCVM"]:
                match_isin = re.search(self.REGEX_ISIN, text)
                if match_isin:
                    isin = match_isin.group(1)
                    self._debug(f"Compte et ISIN : {self.accountList[compte]}:{isin}")
                    return f"{self.accountList[compte]}:{isin}"
            elif self.type in ["DividendeBourse", "EspeceDividende"]:
                return f"{self.accountList[compte]}:Cash"
            else:
                return self.accountList[compte]

    def file_date(self, file):
        """
        Extrait et retourne la date du relevé.

        :param file: Le fichier à traiter
        :type file: object
        :return: La date du relevé
        :rtype: datetime.date
        """
        text = file.convert(pdf_to_text)
        match = re.search(self.DATE_REGEX, text)
        if match:
            return parse_datetime(match.group(1), dayfirst="True").date()

    def _parse_decimal(self, value: str) -> Decimal:
        """
        Parse une chaîne en Decimal en gérant les différents formats.

        :param value: La chaîne à parser
        :type value: str
        :return: La valeur décimale
        :rtype: Decimal
        """
        return Decimal(value.replace(",", ".").replace(" ", "").replace("\xa0", "").replace(r"\u00a", ""))

    def extract(self, file, existing_entries=None):
        """
        Extrait les données du fichier PDF et retourne une liste d'entrées.

        :param file: Le fichier à traiter
        :type file: object
        :param existing_entries: Les entrées existantes, par défaut None
        :type existing_entries: list, optional
        :return: Une liste d'entrées extraites
        :rtype: list
        """
        document = str(self.file_date(file)) + " " + self.file_name(file)
        text = file.convert(pdf_to_text)
        entries = []

        self._debug(f"Contenu du PDF :\n{text}")
        self._debug(f"Type de document : {self.type}")

        extract_methods = {
            "DividendeBourse": self._extract_dividende_bourse,
            "EspeceBourse": self._extract_espece_bourse,
            "Bourse": self._extract_bourse,
            "OPCVM": self._extract_opcvm,
            "Compte": self._extract_compte,
            "Amortissement": self._extract_amortissement,
            "CB": self._extract_cb
        }

        extract_method = extract_methods.get(self.type)
        if extract_method:
            entries.extend(extract_method(file, text, document))

        return entries

    def _extract_dividende_bourse(self, file, text, document):
        """
        Extrait les données pour les dividendes boursiers.

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
        compte = self.file_account(file)
        control = self.REGEX_DIVIDENDE_DETAILS
        chunks = re.findall(control, text)
        meta = data.new_metadata(file.name, 0)
        meta["source"] = "pdfbourso"
        meta["document"] = document
        
        for chunk in chunks:
            print(chunk)
            postings = [
                self._create_posting("Revenus:Dividendes", self._parse_decimal(chunk[4]) * -1, "EUR"),
                self._create_posting("Depenses:Impots:IR", self._parse_decimal(chunk[5] or '0') + self._parse_decimal(chunk[6]), "EUR"),
                self._create_posting(compte, self._parse_decimal(chunk[7]), "EUR")
            ]
            
            transaction = self._create_transaction(
                meta,
                parse_datetime(chunk[0], dayfirst="True").date(),
                f"Dividende pour {chunk[1]} titres {chunk[2]}",
                None,
                {chunk[3]},
                postings
            )
            entries.append(transaction)
        
        return entries

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
        print(self.file_account(file))
        control = self.REGEX_ESPECE_BOURSE_SOLDE
        chunks = re.findall(control, text)
        meta = data.new_metadata(file.name, 0)
        meta["source"] = "pdfbourso"
        meta["document"] = document
        
        for chunk in chunks:
            print(chunk[0])
            print(chunk[1])
            balance = data.Balance(
                meta,
                parse_datetime(chunk[0], dayfirst="True").date(),
                self.file_account(file) + ":Cash",
                amount.Amount(self._parse_decimal(chunk[1]), "EUR"),
                None,
                None,
            )
            entries.append(balance)
        
        return entries

    def _extract_bourse(self, file, text, document):
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

        match = re.search(self.REGEX_BOURSE_MONTANT, text)
        if match:
            ope["Montant Total"] = match.group(5)
            ope["currency Total"] = match.group(6)
        else:
            print("Montant introuvable")
        self._debug(f"Montant Total : {ope['Montant Total']}")
        self._debug(f"Devise Total : {ope['currency Total']}")

        match = re.search(self.REGEX_BOURSE_FRAIS, text)
        if match:
            ope["Frais"] = match.group(5)
            ope["currency Frais"] = match.group(6)
        else:
            print("Frais introuvable")

        match = re.search(self.REGEX_ISIN, text)
        if match:
            ope["ISIN"] = match.group(1)
        else:
            print("ISIN introuvable")

        match = re.search(self.REGEX_BOURSE_DETAILS, text)
        if match:
            ope["Date"] = match.group(1)
            ope["Quantité"] = match.group(2)
            ope["Designation"] = match.group(3)
        else:
            print("Date, Qté, Designation introuvable")

        match = re.search(self.REGEX_BOURSE_COURS, text)
        if match:
            ope["Cours"] = match.group(1)
            ope["currency Cours"] = match.group(2)
        else:
            print("Coursintrouvable")
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
                    None,
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

        meta = data.new_metadata(file.name, 0)
        meta["source"] = "pdfbourso"
        meta["document"] = document

        transaction = self._create_transaction(
            meta,
            parse_datetime(ope["Date"], dayfirst="True").date(),
            ope["Designation"] or "inconnu",
            ope["ISIN"],
            data.EMPTY_SET,
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
            print("Montant introuvable")
        self._debug(f"Montant Total : {ope['Montant Total']}")
        self._debug(f"Devise Total : {ope['currency Total']}")

        match = re.search(self.REGEX_ISIN, text)
        if match:
            ope["ISIN"] = match.group(1)
        else:
            print("ISIN introuvable")

        match = re.search(self.REGEX_OPCVM_DETAILS, text)
        if match:
            ope["Date"] = match.group(1)
            ope["Quantité"] = match.group(2)
            ope["Designation"] = match.group(3)
        else:
            print("Date, Qté, Designation introuvable")

        match = re.search(self.REGEX_OPCVM_COURS, text)
        if match:
            ope["Cours"] = match.group(1)
            ope["currency Cours"] = match.group(2)
        else:
            print("Coursintrouvable")
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
                    None,
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

        meta = data.new_metadata(file.name, 0)
        meta["source"] = "pdfbourso"
        meta["document"] = document

        transaction = self._create_transaction(
            meta,
            parse_datetime(ope["Date"], dayfirst="True").date(),
            ope["Designation"] or "inconnu",
            ope["ISIN"],
            data.EMPTY_SET,
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

        # Affichage du solde initial
        match = re.search(self.REGEX_SOLDE_INITIAL, text)
        datebalance = ""
        balance = ""
        if match:
            datebalance = parse_datetime(
                match.group(2), dayfirst="True"
            ).date() + datetime.timedelta(1)
            longueur = (
                len(match.group(1))
                + len(match.group(3))
                + len(match.group(2))
                + len(match.group(4))
            )
            balance = match.group(4).replace(".", "").replace(",", ".")
            if longueur < 84:
                # Si la distance entre les 2 champs est petite, alors, c'est un débit.
                balance = "-" + balance

        meta = data.new_metadata(file.name, 0)
        meta["source"] = "pdfbourso"
        meta["document"] = document

        entries.append(
            data.Balance(
                meta,
                datebalance,
                self.accountList[compte],
                amount.Amount(D(balance), "EUR"),
                None,
                None,
            )
        )

        chunks = re.findall(self.REGEX_OPERATION_COMPTE, text)

        # Si debogage, affichage de l'extraction
        self._debug(f"Chunks extraits : {chunks}")

        index = 0
        for chunk in chunks:
            index += 1
            meta = data.new_metadata(file.name, index)
            meta["source"] = "pdfbourso"
            meta["document"] = document
            ope = dict()

            # Si debogage, affichage de l'extraction
            self._debug(f"Chunk extrait : {chunk}")

            ope["date"] = chunk[1]
            # Si debogage, affichage de l'extraction
            self._debug(f"Date de l'opération : {ope['date']}")

            ope["montant"] = chunk[3].replace(".", "").replace(",", ".")
            # Si debogage, affichage de l'extraction
            self._debug(f"Montant de l'opération : {ope['montant']}")

            # Longueur de l'espace intercalaire
            longueur = (
                len(chunk[0])
                + len(chunk[1])
                + len(chunk[2])
                + len(chunk[3])
            )
            # Si debogage, affichage de l'extraction
            self._debug(f"Longueur de l'espace intercalaire : {longueur}")

            if longueur > 148:
                ope["type"] = "Credit"
            else:
                ope["type"] = "Debit"
                ope["montant"] = "-" + ope["montant"]
            # Si débogage, affichage de l'extraction
            self._debug(f"Montant de l'opération : {ope['montant']}")

            ope["payee"] = re.sub(r"\s+", " ", chunk[0])
            # Si debogage, affichage de l'extraction
            self._debug(f"Payee : {ope['payee']}")

            ope["narration"] = re.sub(r"\s+", " ", chunk[4])
            # Si debogage, affichage de l'extraction
            self._debug(f"Narration : {ope['narration']}")

            # Creation de la transaction
            postings = [
                self._create_posting(
                    self.accountList[compte],
                    Decimal(ope["montant"]),
                    "EUR",
                ),
            ]
            transaction = self._create_transaction(
                meta,
                parse_datetime(ope["date"], dayfirst="True").date(),
                ope["payee"] or "inconnu",
                ope["narration"],
                data.EMPTY_SET,
                postings,
            )
            entries.append(transaction)

        # Recherche du solde final
        match = re.search(self.REGEX_SOLDE_FINAL, text)
        if match:
            balance = match.group(2).replace(".", "").replace(",", ".")
            longueur = len(match.group(1))
            if self.debug:
                print(balance)
                print(longueur)
            if longueur < 84:
                # Si la distance entre les 2 champs est petite, alors, c'est un débit.
                balance = "-" + balance
            # Recherche de la date du solde final
            match = re.search(self.REGEX_DATE_SOLDE_FINAL, text)
            if match:
                datebalance = parse_datetime(
                    match.group(1), dayfirst="True"
                ).date()
                if self.debug:
                    print(datebalance)
                meta = data.new_metadata(file.name, 0)
                meta["source"] = "pdfbourso"
                meta["document"] = document

                entries.append(
                    data.Balance(
                        meta,
                        datebalance,
                        self.accountList[compte],
                        amount.Amount(D(balance), "EUR"),
                        None,
                        None,
                    )
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
            meta = data.new_metadata(file.name, index)
            meta["source"] = "pdfbourso"

            ope = dict()
            ope["date"] = parse_datetime(chunk[0], dayfirst="True").date()
            ope["prelevement"] = amount.Amount(
                self._parse_decimal(chunk[1])*-1, "EUR"
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
                )
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
            meta = data.new_metadata(file.name, index)
            meta["source"] = "pdfbourso"
            meta["document"] = document
            ope = dict()

            # Si debogage, affichage de l'extraction
            self._debug(f"Chunk extrait : {chunk}")

            ope["date"] = chunk[0]
            # Si debogage, affichage de l'extraction
            self._debug(f"Date de l'opération : {ope['date']}")

            ope["montant"] = self._parse_decimal(chunk[2])*-1
            # Si debogage, affichage de l'extraction
            self._debug(f"Montant de l'opération : {ope['montant']}")

            ope["payee"] = re.sub(r"\s+", " ", chunk[1])
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
            transaction = self._create_transaction(
                meta,
                parse_datetime(ope["date"], dayfirst="True").date(),
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
                    match.group(1), dayfirst="True"
                ).date()
                self._debug(f"Date de la balance : {datebalance}")
                meta = data.new_metadata(file.name, 0)
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
                    )
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
        return data.Transaction(
            meta=meta,
            date=date,
            flag=flags.FLAG_OKAY,
            payee=payee,
            narration=narration,
            tags=tags,
            links=data.EMPTY_SET,
            postings=postings,
        )
