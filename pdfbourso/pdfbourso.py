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

    # Constantes de classe pour les motifs regex
    REGEX_DIVIDENDE = r"COUPONS REMBOURSEMENTS :"
    REGEX_ESPECE_BOURSE = r"RELEVE COMPTE ESPECES :"
    REGEX_BOURSE = r"OPERATION DE BOURSE"
    REGEX_OPCVM = r"OPERATION SUR OPC"
    REGEX_CB = r"Relevé de Carte"
    REGEX_COMPTE = r"BOURSORAMA BANQUE|BOUSFRPPXXX|RCS\sNanterre\s351\s?058\s?151"
    REGEX_AMORTISSEMENT = r"tableau d'amortissement|Echéancier Prévisionnel|Échéancier Définitif"

    REGEX_COMPTE_COMPTE = r"\s*(\d{11})"
    REGEX_COMPTE_CB = r"\s*((4979|4810)\*{8}\d{4})"
    REGEX_COMPTE_AMORTISSEMENT = r"N(?:°|º) du crédit\s*:\s?(\d{5}\s?-\s?\d{11})"
    REGEX_COMPTE_ESPECE_DIVIDENDE_BOURSE = r"40618\s\d{5}\s(\d{11})\s"
    REGEX_COMPTE_BOURSE_OPCVM = r"\d{5}\s\d{5}\s(\d{11})\s"
    REGEX_ISIN = r"Code ISIN\s:\s*([A-Z,0-9]{12})"

    DATE_REGEX = r"(?:le\s|au\s*|Date départ\s*:\s)(\d*/\d*/\d*)"

    def __init__(self, accountList, debug: bool = False):
        """
        Cette fonction est utilisée pour créer une instance de la classe.
        Elle prend une liste de comptes comme paramètre et renvoie une instance de la classe.
        La classe a deux attributs : une liste de comptes et un indicateur de débogage booléen.

        :param accountList: Un dictionnaire de comptes
        :param debug: bool = False, par défaut False
        :type debug: bool (optionnel)
        :return: None
        """
        assert isinstance(accountList, dict), "La liste de comptes doit être de type dict"
        self.accountList = accountList
        self.debug = debug

    def _debug(self, message: str):
        """
        Affiche un message de débogage si le mode debug est activé.

        Args:
            message (str): Le message à afficher.
        """
        if self.debug:
            print(f"[DEBUG] {message}")

    def identify(self, file):
        """
        La fonction identify prend un fichier comme argument et renvoie une valeur booléenne.
        Si le fichier est un pdf, il le convertit en texte et vérifie si le texte contient
        certains mots-clés. S'il les contient, il renvoie True.
        Sinon, il renvoie False.

        :param file: le fichier à traiter
        :return: Le type du fichier.
        """
        if file.mimetype() != "application/pdf":
            return False

        text = file.convert(pdf_to_text)
        self._debug(f"Contenu du PDF :\n{text}")
        if text:
            if re.search(self.REGEX_DIVIDENDE, text) is not None:
                self.type = "DividendeBourse"
                return 1
            if re.search(self.REGEX_ESPECE_BOURSE, text) is not None:
                self.type = "EspeceBourse"
                return 1
            if re.search(self.REGEX_BOURSE, text) is not None:
                self.type = "Bourse"
                return 1
            if re.search(self.REGEX_OPCVM, text) is not None:
                self.type = "OPCVM"
                return 1
            if re.search(self.REGEX_CB, text) is not None:
                self.type = "CB"
                return 1
            if re.search(self.REGEX_COMPTE, text) is not None:
                self.type = "Compte"
                return 1
            if re.search(self.REGEX_AMORTISSEMENT, text) is not None:
                self.type = "Amortissement"
                return 1

    def file_name(self, file):
        # Normalize the name to something meaningful.
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
        The function file_account() takes a file object as an argument and returns the account number
        associated with the file.

        :param file: the file to convert
        :return: The account number.
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
        It takes a file object as an argument, converts it to text, and then searches for the date in the
        text. If it finds a date, it parses it and returns it as a datetime object.

        :param file: The file to convert
        :return: The date of the statement.
        """
        text = file.convert(pdf_to_text)
        match = re.search(self.DATE_REGEX, text)
        if match:
            return parse_datetime(match.group(1), dayfirst="True").date()

    def _parse_decimal(self, value: str) -> Decimal:
        """Parse une chaîne en Decimal en gérant les différents formats."""
        return Decimal(value.replace(",", ".").replace(" ", "").replace("\xa0", "").replace(r"\u00a", ""))

    def extract(self, file, existing_entries=None):
        """
        Extrait les données du fichier PDF et retourne une liste d'entrées.
        """
        document = str(self.file_date(file)) + " " + self.file_name(file)
        text = file.convert(pdf_to_text)
        entries = []

        self._debug(f"Contenu du PDF :\n{text}")
        self._debug(f"Type de document : {self.type}")

        if self.type == "DividendeBourse":
            entries.extend(self._extract_dividende_bourse(file, text, document))
        elif self.type == "EspeceBourse":
            entries.extend(self._extract_espece_bourse(file, text, document))
        elif self.type == "Bourse":
            entries.extend(self._extract_bourse(file, text, document))
        elif self.type == "OPCVM":
            entries.extend(self._extract_opcvm(file, text, document))
        elif self.type == "Compte":
            entries.extend(self._extract_compte(file, text, document))
        elif self.type == "Amortissement":
            entries.extend(self._extract_amortissement(file, text, document))
        elif self.type == "CB":
            entries.extend(self._extract_cb(file, text, document))

        return entries

    def _extract_dividende_bourse(self, file, text, document):
        """Extrait les données pour les dividendes boursiers."""
        entries = []
        compte = self.file_account(file)
        control = r"(\d{2}\/\d{2}\/\d{4})\s*(\d{1,5})\s*(.*)\s\(([A-Z]{2}[A-Z,0-9]{10})\)\s*(\d{0,3}\s\d{1,3}[,.]\d{2})\s*(\d{0,3}\s\d{1,3}[,.]\d{2})?\s*(\d{0,3}\s\d{1,3}[,.]\d{2})\s*(\d{0,3}\s\d{1,3}[,.]\d{2})\s*(\d{0,3}\s\d{1,3}[,.]\d{2})"
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
        """Extrait les données pour les espèces en bourse."""
        entries = []
        print(self.file_account(file))
        control = r"(\d*/\d*/\d*).*SOLDE\s*(\d{0,3}\s\d{1,3}[,.]\d{1,3})"
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
        """Extrait les données pour les opérations boursières."""
        entries = []
        # Identification du numéro de compte
        control = r"\d{5}\s\d{5}\s(\d{11})\s"
        match = re.search(control, text)
        if match:
            compte = match.group(1)

        # Si débogage, affichage de l'extraction
        self._debug(f"Numéro de compte extrait : {compte}")

        ope = dict()

        control = r"Montant transaction\s*Montant transaction brut\s*Intérêts\s*total brut\s*Courtages\s*Montant transaction net\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*"
        match = re.search(control, text)
        if match:
            ope["Montant Total"] = match.group(5)
            ope["currency Total"] = match.group(6)
        else:
            print("Montant introuvable")
        self._debug(f"Montant Total : {ope['Montant Total']}")
        self._debug(f"Devise Total : {ope['currency Total']}")

        control = r"Commission\s*Frais divers\s*Montant total des frais\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*"
        match = re.search(control, text)
        if match:
            ope["Frais"] = match.group(5)
            ope["currency Frais"] = match.group(6)
        else:
            print("Frais introuvable")

        control = r"Code ISIN\s:\s*([A-Z,0-9]{12})"
        match = re.search(control, text)
        if match:
            ope["ISIN"] = match.group(1)
        else:
            print("ISIN introuvable")

        control = r"locale d'exécution\s*Quantité\s*Informations sur la valeur\s*Informations sur l'exécution\s*(\d{1,2}\/\d{2}\/\d{4})\s*(\d{0,3}\s\d{1,3})\s*([\s\S]{0,20})?\s*"
        match = re.search(control, text)
        if match:
            ope["Date"] = match.group(1)
            ope["Quantité"] = match.group(2)
            ope["Designation"] = match.group(3)
        else:
            print("Date, Qté, Designation introuvable")

        control = r"Cours exécuté :\s*(\d{0,3}\s\d{1,3}[,.]\d{0,4})\s([A-Z]{1,3})"
        match = re.search(control, text)
        if match:
            ope["Cours"] = match.group(1)
            ope["currency Cours"] = match.group(2)
        else:
            print("Coursintrouvable")
        self._debug(f"Date de l'opération : {ope['Date']}")

        control = r"ACHAT COMPTANT"
        match = re.search(control, text)
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
        """Extrait les données pour les opérations OPCVM."""
        entries = []
        # Identification du numéro de compte
        control = r"\d{5}\s\d{5}\s(\d{11})\s"
        match = re.search(control, text)
        if match:
            compte = match.group(1)

        # Si débogage, affichage de l'extraction
        self._debug(f"Numéro de compte extrait : {compte}")

        ope = dict()

        control = r"Montant brut\s*Droits d'entrée\s*Frais H.T.\s*T.V.A.\s*Montant net au débit de votre compte\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s*(\d{0,3}\s*\d{1,3}[,.]\d{1,3})\s([A-Z]{3})\s"
        match = re.search(control, text)
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

        control = r"Code ISIN\s:\s*([A-Z,0-9]{12})"
        match = re.search(control, text)
        if match:
            ope["ISIN"] = match.group(1)
        else:
            print("ISIN introuvable")

        control = r"(\d{1,2}\/\d{2}\/\d{4})\s*(\d{0,3}\s\d{1,3}[.,]?\d{0,4})\s*([\s\S]{0,20})?\s*"
        match = re.search(control, text)
        if match:
            ope["Date"] = match.group(1)
            ope["Quantité"] = match.group(2)
            ope["Designation"] = match.group(3)
        else:
            print("Date, Qté, Designation introuvable")

        control = r"Valeur liquidative :\s*(\d{0,3}\s\d{1,3}[,.]\d{0,4})\s([A-Z]{1,3})"
        match = re.search(control, text)
        if match:
            ope["Cours"] = match.group(1)
            ope["currency Cours"] = match.group(2)
        else:
            print("Coursintrouvable")
        self._debug(f"Cours : {ope['Cours']}")

        control = r"SOUSCRIPTION"
        match = re.search(control, text)
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
        """Extrait les données pour les opérations de compte."""
        entries = []
        # Identification du numéro de compte
        control = r"\s*\d{11}"
        match = re.search(control, text)
        if match:
            compte = match.group(0).split(" ")[-1]

        # Si debogage, affichage de l'extraction
        self._debug(f"Numéro de compte extrait : {compte}")

        # Affichage du solde initial
        control = r"SOLDE\s(?:EN\sEUR\s+)?AU\s:(\s+)(\d{1,2}\/\d{2}\/\d{4})(\s+)((?:\d{1,3}\.)?\d{1,3},\d{2})"
        match = re.search(control, text)
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

        control = r"\d{1,2}\/\d{2}\/\d{4}\s(.*)\s(\d{1,2}\/\d{2}\/\d{4})\s(\s*)\s((?:\d{1,3}\.)?\d{1,3},\d{2})(?:(?:\n.\s{8,20})(.+?))?\n"  # regexr.com/4ju06
        chunks = re.findall(control, text)

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
        control = r"Nouveau solde en EUR :(\s+)((?:\d{1,3}\.)?(?:\d{1,3}\.)?\d{1,3},\d{2})"
        match = re.search(control, text)
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
            control = r"(\d{1,2}\/\d{2}\/\d{4}).*40618"
            match = re.search(control, text)
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
        """Extrait les données pour les opérations d'amortissement."""
        entries = []
        # Identification du numéro de compte
        control = r"N(?:°|º) du crédit\s*:\s?(\d{5}\s?-\s?\d{11})"
        match = re.search(control, text)
        if match:
            compte = match.group(1)

        # Si debogage, affichage de l'extraction
        self._debug(f"Numéro de compte : {compte}")

        control = r"(\d*/\d*/\d*)\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})\s+(\d+.\d{2})"
        chunks = re.findall(control, text)

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
        """Extrait les données pour les opérations CB."""
        entries = []
        # Identification du numéro de compte
        control = r"\s*((4979|4810)\*{8}\d{4})"
        match = re.search(control, text)
        if match:
            compte = match.group(1)

        # Si debogage, affichage de l'extraction
        self._debug(f"Numéro de compte : {compte}")

        control = r"(\d{1,2}\/\d{2}\/\d{4})\s*CARTE\s(.*)\s((?:\d{1,3}\.)?\d{1,3},\d{2})"
        chunks = re.findall(control, text)

        # Si debogage, affichage de l'extraction
        self._debug(f"Expression régulière utilisée : {control}")
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
        control = r"A VOTRE DEBIT LE\s(\d{1,2}\/\d{2}\/\d{4})\s*((?:\d{1,3}\.)?(?:\d{1,3}\.)?\d{1,3},\d{2})"
        match = re.search(control, text)
        if match:
            balance = self._parse_decimal(match.group(2))*-1
            self._debug(f"Balance : {balance}")
            # Recherche de la date du solde final
            control = r"(\d{1,2}\/\d{2}\/\d{4}).*40618"
            match = re.search(control, text)
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
        """Crée un posting pour une transaction."""
        return data.Posting(
            account=account,
            units=amount.Amount(amount_value, currency),
            cost=cost,
            flag=None,
            meta=None,
            price=price,
        )

    def _create_transaction(self, meta, date, payee, narration, tags, postings):
        """Crée une transaction."""
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
