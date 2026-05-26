import datetime as dt
from decimal import Decimal

from beancount.core import data

from . import pdfbanquepopulaire


ACCOUNTLIST = {
    "12345678901": "Actif:BanquePopulaire:CCPrincipal",
    "99999999999": "Actif:BPop:CCSecondaire",
}

SYNTHETIC_STATEMENT = """BANQUE POPULAIRE
Votre relevé de compte n°1 au 31/03/2026
DETAIL DES OPERATIONS DE VOTRE COMPTE CHEQUES N° 12345678901

SOLDE CREDITEUR AU 07/03/2026                                                                                     0,00 €
21/03             VIR INST VIREMENT TEST                                                                          ABC1234              21/03                 21/03                            500,00 €
                    REFERENCE INTERNE DE TEST
23/03             210326 CB****1234                                                                               TCK1234              23/03                 23/03                            - 60,00 €
                    COMMERCE TEST
28/03    F        COTIS CARTE TEST
                    CONTRAT CARTE ********1234
                    9999001              27/03                 27/03                          - 136,30 €
                    COTISATION MENSUELLE

TOTAL DES MOUVEMENTS DEBITEURS                                                                                  - 196,30 €
TOTAL DES MOUVEMENTS CREDITEURS                                                                                  500,00 €

SOLDE DEBITEUR AU 31/03/2026*                                                                                    - 61,20 €
"""


def test_identify_date_and_account(monkeypatch):
    monkeypatch.setattr(
        pdfbanquepopulaire,
        "pdf_to_text",
        lambda _: SYNTHETIC_STATEMENT,
    )
    importer = pdfbanquepopulaire.PDFBanquePopulaire(ACCOUNTLIST)

    assert importer.identify("statement.pdf")
    assert importer.filename("statement.pdf") == "Relevé Compte.pdf"
    assert importer.account("statement.pdf") == "Actif:BanquePopulaire:CCPrincipal"
    assert importer.date("statement.pdf") == dt.date(2026, 3, 31)


def test_extract_transactions_and_balances(monkeypatch):
    monkeypatch.setattr(
        pdfbanquepopulaire,
        "pdf_to_text",
        lambda _: SYNTHETIC_STATEMENT,
    )
    importer = pdfbanquepopulaire.PDFBanquePopulaire(ACCOUNTLIST)

    entries = importer.extract("statement.pdf")

    balances = [entry for entry in entries if isinstance(entry, data.Balance)]
    transactions = [
        entry for entry in entries if isinstance(entry, data.Transaction)
    ]

    assert [entry.amount.number for entry in balances] == [
        Decimal("0.00"),
        Decimal("-61.20"),
    ]
    assert [entry.date for entry in balances] == [
        dt.date(2026, 3, 8),
        dt.date(2026, 3, 31),
    ]

    assert [entry.postings[0].units.number for entry in transactions] == [
        Decimal("500.00"),
        Decimal("-60.00"),
        Decimal("-136.30"),
    ]
    assert transactions[0].payee == "VIR INST VIREMENT TEST"
    assert transactions[0].narration == "REFERENCE INTERNE DE TEST"
    assert transactions[2].payee == "COTIS CARTE TEST"
    assert (
        transactions[2].narration
        == "CONTRAT CARTE ********1234 COTISATION MENSUELLE"
    )
    assert all(
        entry.meta["source"] == "pdfbanquepopulaire" for entry in entries
    )


def test_resolve_partial_date_rolls_back_previous_year():
    importer = pdfbanquepopulaire.PDFBanquePopulaire(ACCOUNTLIST)

    assert importer._resolve_partial_date(
        "30/12", dt.date(2026, 1, 31)
    ) == dt.date(2025, 12, 30)


SYNTHETIC_BP_CCTIM_STATEMENT = """BANQUE POPULAIRE
Votre relevé de compte n°1 au 01/04/2026
DETAIL DES OPERATIONS DE VOTRE COMPTE CHEQUES N° 99999999999

SOLDE CREDITEUR AU 07/03/2026                                                                                     0,00 €
28/03             COTIS VISA PREMIER DD
                    XSYNTH01 2026042700099990000001
                    CONTRAT CARTE ********788J
                    9999002              27/03                 27/03                          - 136,30 €

TOTAL DES MOUVEMENTS DEBITEURS                                                                                  - 136,30 €
TOTAL DES MOUVEMENTS CREDITEURS                                                                                    0,00 €

SOLDE DEBITEUR AU 01/04/2026*                                                                                  - 136,30 €
"""


def test_extract_bpop_cctim_statement(monkeypatch):
    monkeypatch.setattr(
        pdfbanquepopulaire,
        "pdf_to_text",
        lambda _: SYNTHETIC_BP_CCTIM_STATEMENT,
    )
    importer = pdfbanquepopulaire.PDFBanquePopulaire(ACCOUNTLIST)

    assert importer.account("statement.pdf") == "Actif:BPop:CCSecondaire"

    entries = importer.extract("statement.pdf")
    balances = [entry for entry in entries if isinstance(entry, data.Balance)]
    transactions = [
        entry for entry in entries if isinstance(entry, data.Transaction)
    ]

    assert [entry.amount.number for entry in balances] == [
        Decimal("0.00"),
        Decimal("-136.30"),
    ]
    assert [entry.date for entry in balances] == [
        dt.date(2026, 3, 8),
        dt.date(2026, 4, 1),
    ]
    assert len(transactions) == 1
    assert transactions[0].payee == "COTIS VISA PREMIER DD"
    assert (
        transactions[0].narration
        == "XSYNTH01 2026042700099990000001 CONTRAT CARTE ********788J"
    )
    assert [posting.account for posting in transactions[0].postings] == [
        "Actif:BPop:CCSecondaire",
    ]
    assert transactions[0].postings[0].units.number == Decimal("-136.30")


SYNTHETIC_BP_CCSCI_STATEMENT = """BANQUE POPULAIRE
Votre relevé de compte n°3 au 31/03/2026
DETAIL DES OPERATIONS DE VOTRE COMPTE COURANT N° 22334455667

SOLDE CREDITEUR AU 27/02/2026                                                                                 31 000,00 €
02/03             PRLV SEPA FOURNISSEUR TEST                                                            05G1U1S              02/03                 02/03                         - 1 380,00 €
                    DOSSIER TEST 001
                    REFERENCE TEST B13-001
18/03             EVI ME PRESTATAIRE TEST                                                             SK3RTPF              18/03                 18/03                            480,00 €
                    REGLEMENT DOSSIER TEST 01
                    POUR FACTURE TEST AUGUSTA

TOTAL DES MOUVEMENTS DEBITEURS                                                                             - 1 380,00 €
TOTAL DES MOUVEMENTS CREDITEURS                                                                                480,00 €

SOLDE CREDITEUR AU 31/03/2026*                                                                              30 100,00 €
"""


def test_identify_current_account_statement(monkeypatch):
    monkeypatch.setattr(
        pdfbanquepopulaire,
        "pdf_to_text",
        lambda _: SYNTHETIC_BP_CCSCI_STATEMENT,
    )
    importer = pdfbanquepopulaire.PDFBanquePopulaire(
        {**ACCOUNTLIST, "22334455667": "Actif:Tests:CCSCI"}
    )

    assert importer.identify("statement.pdf")
    assert importer.account("statement.pdf") == "Actif:Tests:CCSCI"
    assert importer.date("statement.pdf") == dt.date(2026, 3, 31)


SYNTHETIC_BP_CCSCI_WITH_SEPA_SECTION = """BANQUE POPULAIRE
Votre relevé de compte n°3 au 31/03/2026
DETAIL DES OPERATIONS DE VOTRE COMPTE COURANT N° 22334455667

SOLDE CREDITEUR AU 27/02/2026                                                                                 31 000,00 €
02/03             PRLV SEPA FOURNISSEUR TEST                                                            05G1U1S              02/03                 02/03                         - 1 380,00 €
                    DOSSIER TEST 001
                    REFERENCE TEST B13-001
18/03             EVI ME PRESTATAIRE TEST                                                             SK3RTPF              18/03                 18/03                            480,00 €
                    REGLEMENT DOSSIER TEST 01
                    POUR FACTURE TEST AUGUSTA

SOLDE CREDITEUR AU 31/03/2026*
(*) Sous réserve des opérations en cours d'enregistrement.
Ce document ne justifie pas la déduction de la TVA.
DETAIL DE VOS MOUVEMENTS SEPA
"""


def test_extract_current_account_without_totals_block(monkeypatch):
    monkeypatch.setattr(
        pdfbanquepopulaire,
        "pdf_to_text",
        lambda _: SYNTHETIC_BP_CCSCI_WITH_SEPA_SECTION,
    )
    importer = pdfbanquepopulaire.PDFBanquePopulaire(
        {**ACCOUNTLIST, "22334455667": "Actif:Tests:CCSCI"}
    )

    entries = importer.extract("statement.pdf")
    transactions = [
        entry for entry in entries if isinstance(entry, data.Transaction)
    ]

    assert len(transactions) == 2
    assert transactions[0].payee == "PRLV SEPA FOURNISSEUR TEST"
    assert transactions[1].payee == "EVI ME PRESTATAIRE TEST"


SYNTHETIC_BP_CCSCI_OCR_CORRUPTED_STATEMENT = """BANQUE POPULAIRE
Votre relevé de compte n°4 au 30/04/2026
DETAIL DES OPERATIONS DE VOTRE COMPTE COURANT N° 12345678901

SOLDE CREDITEUR AU 31/03/2026                                                                                  7 714,94 €
07/04               ARRETE DE CPTE                                                                     1111111                07/04                    31/03                                 -6175€
                      1 ER TRIMESTRE 2026
08/04                PRLV SEPA 0042 SYNDIC EXEM                                                        SYNTH01                07/04                   07/04                            73 639.47 €
                      Paiement de la facture Telepaiem
                      2026042800000SYNTHETIC001
09/04                ECHEANCE PRET                                                                     9111111                07/04                   06/04                                 - 249,08 €
                      DONT CAP           0,00 ASS.      0,00E
                      INT,   249,08 COM.         0,00E
10/04                FRAIS MANDAT PRLV SEPA                                                            9999003                09/04                   09/04                                   - 1,00 €
                     XSYNTH03 202605099999003000001
                      CREANCIER            0042 SYNDIC EXEMPLE

                                S DEBITEURS
TOTAL DES MOUVEMENTS CREDITEURS                                                                                                                                                0,00 €

SOLDE CREDITEUR AU 30/04/2026*
(*) Sous réserve des opérations en cours d'enregistrement et d'une provision suffisante et disponible lors de l'arrêté du solde du compte réalisé en fin de journée.
Ce document ne justifie pas la déduction de la TVA ou de la charge en matière d'impôt direct.

DETAIL DE VOS MOUVEMENTS SEPA
VOTRE COMPTE COURANT N° 12345 678901 RELEVE N° 4 AU 30/04/2026
DATE DETAIL DE VOS PRELEVEMENTS SEPA RECUS DEBIT
07/04 0042 SYNDIC EXEMPLE ALPHA FR76123Z45TEST4 3 639,47 €
2026042800000SYNTHETIC001 144-1
Paiement de la facture Telepaiement du 01/04/2026 RESIDENCE TEST 01
"""


SYNTHETIC_BP_CCSCI_ONLY_CLOSING_BALANCE = """BANQUE POPULAIRE
Votre relevé de compte n°4 au 30/04/2026
DETAIL DES OPERATIONS DE VOTRE COMPTE COURANT N° 12345678901

SOLDE CREDITEUR AU 31/03/2026
07/04               ARRETE DE CPTE                                                                     1111111                07/04                    31/03                                 -6175€
                      1 ER TRIMESTRE 2026
TOTAL DES MOUVEMENTS DEBITEURS                                                                                 - 61,75 €
TOTAL DES MOUVEMENTS CREDITEURS                                                                                                                                                0,00 €

SOLDE CREDITEUR AU 30/04/2026                                                                                  7 653,19 €
"""


def test_extract_current_account_with_ocr_corrupted_amounts(monkeypatch):
    monkeypatch.setattr(
        pdfbanquepopulaire,
        "pdf_to_text",
        lambda _: SYNTHETIC_BP_CCSCI_OCR_CORRUPTED_STATEMENT,
    )
    importer = pdfbanquepopulaire.PDFBanquePopulaire(
        {**ACCOUNTLIST, "12345678901": "Actif:Tests:CCSCI"}
    )

    entries = importer.extract("statement.pdf")
    balances = [entry for entry in entries if isinstance(entry, data.Balance)]
    transactions = [
        entry for entry in entries if isinstance(entry, data.Transaction)
    ]

    assert [entry.amount.number for entry in balances] == [
        Decimal("7714.94"),
        Decimal("3763.64"),
    ]
    assert [entry.date for entry in balances] == [
        dt.date(2026, 4, 1),
        dt.date(2026, 4, 30),
    ]
    assert [entry.postings[0].units.number for entry in transactions] == [
        Decimal("-61.75"),
        Decimal("-3639.47"),
        Decimal("-249.08"),
        Decimal("-1.00"),
    ]
    assert transactions[0].payee == "ARRETE DE CPTE"
    assert transactions[0].narration == "1 ER TRIMESTRE 2026"
    assert transactions[1].payee == "PRLV SEPA 0042 SYNDIC EXEM"
    assert "2026042800000SYNTHETIC001" in transactions[1].narration


def test_extract_current_account_with_single_closing_balance(monkeypatch):
    monkeypatch.setattr(
        pdfbanquepopulaire,
        "pdf_to_text",
        lambda _: SYNTHETIC_BP_CCSCI_ONLY_CLOSING_BALANCE,
    )
    importer = pdfbanquepopulaire.PDFBanquePopulaire(
        {**ACCOUNTLIST, "12345678901": "Actif:Tests:CCSCI"}
    )

    entries = importer.extract("statement.pdf")
    balances = [entry for entry in entries if isinstance(entry, data.Balance)]
    transactions = [
        entry for entry in entries if isinstance(entry, data.Transaction)
    ]

    assert len(balances) == 1
    assert balances[0].date == dt.date(2026, 4, 30)
    assert balances[0].amount.number == Decimal("7653.19")
    assert [entry.postings[0].units.number for entry in transactions] == [
        Decimal("-61.75")
    ]


# ── Regression: Plus-sign refund (ANN COTIS CARTE) ───────────────────────

SYNTHETIC_COTIS_REFUND = """BANQUE POPULAIRE
Votre relevé de compte n°5 au 30/04/2026
DETAIL DES OPERATIONS DE VOTRE COMPTE CHEQUES N° 12345678901

SOLDE DEBITEUR AU 31/03/2026                                                                                     - 6,55 €
13/04            ANN COTIS CARTE
                        XSYNTH02 2026042700099999000001
                                                CONTRAT CARTE ********792J
                        9999001              13/04                 31/03                            + 130,70 €

TOTAL DES MOUVEMENTS DEBITEURS                                                                                   0,00 €
TOTAL DES MOUVEMENTS CREDITEURS                                                                               130,70 €

SOLDE CREDITEUR AU 30/04/2026*                                                                                 124,15 €
"""


def test_extract_cotis_refund_with_plus_sign(monkeypatch):
    monkeypatch.setattr(
        pdfbanquepopulaire,
        "pdf_to_text",
        lambda _: SYNTHETIC_COTIS_REFUND,
    )
    importer = pdfbanquepopulaire.PDFBanquePopulaire(ACCOUNTLIST)

    entries = importer.extract("statement.pdf")
    transactions = [
        entry for entry in entries if isinstance(entry, data.Transaction)
    ]
    balances = [entry for entry in entries if isinstance(entry, data.Balance)]

    assert len(transactions) == 1
    assert transactions[0].payee == "ANN COTIS CARTE"
    assert transactions[0].postings[0].units.number == Decimal("130.70")
    assert [posting.account for posting in transactions[0].postings] == [
        "Actif:BanquePopulaire:CCPrincipal",
    ]
    assert [entry.amount.number for entry in balances] == [
        Decimal("-6.55"),
        Decimal("124.15"),
    ]


# ── Regression: sign parsing edge cases ──────────────────────────────────

SYNTHETIC_SIGN_EDGE_CASES = """BANQUE POPULAIRE
Votre relevé de compte n°7 au 30/04/2026
DETAIL DES OPERATIONS DE VOTRE COMPTE CHEQUES N° 12345678901

SOLDE CREDITEUR AU 31/03/2026                                                                                     0,00 €
01/04             PRLV SEPA DIRECTION GENE                                                              08CDEFG              01/04                 01/04                          + 124,00 €
                    TF 2026
02/04             COTIS FAMILLE CONFORT                                                                  15JKLMN              02/04                 02/04                          + 12,45 €
03/04             PRLV SEPA URSSAF RHONE A                                                               07BCDEF              03/04                 03/04                         - 113,95 €
                    CESU + MME TEST
04/04             VIR INST VIREMENT TEST                                                                  ABC1234              04/04                 04/04                           500,00 €
                    REFERENCE INTERNE
05/04             210406 CB****1234                                                                       TCK1234              05/04                 05/04                            - 60,00 €
                    COMMERCE TEST

TOTAL DES MOUVEMENTS DEBITEURS                                                                                - 310,40 €
TOTAL DES MOUVEMENTS CREDITEURS                                                                                500,00 €

SOLDE CREDITEUR AU 30/04/2026*                                                                                 189,60 €
"""


def test_sign_edge_cases(monkeypatch):
    """Regression: sign parsing for real-world OCR outputs.

    Covers cases encountered in actual BanquePop statements:
    - PRLV DIRECTION GENE with explicit + sign (TF payment, should be -)
    - COTIS FAMILLE CONFORT with explicit + sign (fee, should be -)
    - PRLV URSSAF with explicit - sign (household charges)
    - VIR without sign (credit, positive)
    - CB transaction with explicit - sign (debit)
    """
    monkeypatch.setattr(
        pdfbanquepopulaire,
        "pdf_to_text",
        lambda _: SYNTHETIC_SIGN_EDGE_CASES,
    )
    importer = pdfbanquepopulaire.PDFBanquePopulaire(ACCOUNTLIST)

    entries = importer.extract("statement.pdf")
    transactions = [
        entry for entry in entries if isinstance(entry, data.Transaction)
    ]
    balances = [entry for entry in entries if isinstance(entry, data.Balance)]

    assert len(transactions) == 5

    # Transaction 0: DIRECTION GENE — OCR says '+', importer faithfully reports +
    assert transactions[0].payee == "PRLV SEPA DIRECTION GENE"
    assert transactions[0].postings[0].units.number == Decimal("124.00")

    # Transaction 1: COTIS FAMILLE CONFORT — OCR says '+', importer reports +
    assert transactions[1].payee == "COTIS FAMILLE CONFORT"
    assert transactions[1].postings[0].units.number == Decimal("12.45")

    # Transaction 2: URSSAF — explicit minus sign correctly parsed as debit
    assert transactions[2].payee == "PRLV SEPA URSSAF RHONE A"
    assert transactions[2].postings[0].units.number == Decimal("-113.95")

    # Transaction 3: VIR — no explicit sign, positive credit
    assert transactions[3].payee == "VIR INST VIREMENT TEST"
    assert transactions[3].postings[0].units.number == Decimal("500.00")

    # Transaction 4: CB — explicit minus sign correctly parsed as debit
    assert transactions[4].postings[0].units.number == Decimal("-60.00")

    # Balances
    assert [entry.amount.number for entry in balances] == [
        Decimal("0.00"),
        Decimal("189.60"),
    ]


# ── Regression: SEPA detail amount override ──────────────────────────────

SYNTHETIC_SEPA_DETAIL_SECTION = """BANQUE POPULAIRE
Votre relevé de compte n°8 au 30/04/2026
DETAIL DES OPERATIONS DE VOTRE COMPTE CHEQUES N° 12345678901

SOLDE CREDITEUR AU 31/03/2026                                                                                     0,00 €
01/04             PRLV SEPA FOURNISSEUR TEST                                                            05G1U1S              01/04                 01/04                         + 1 380,00 €
                    DOSSIER TEST 001
                    2026040100000TESTSYNTH01 144-1
02/04             PRLV SEPA DIRECTION GENE                                                               08CDEFG              02/04                 02/04                          + 124,00 €
                    TF 2026
                    2026040200000TESTSYNTH02
03/04             COTIS FAMILLE CONFORT                                                                  15JKLMN              03/04                 03/04                          + 12,45 €

TOTAL DES MOUVEMENTS DEBITEURS                                                                              - 1 516,45 €
TOTAL DES MOUVEMENTS CREDITEURS                                                                                  0,00 €

SOLDE DEBITEUR AU 30/04/2026*                                                                              - 1 516,45 €

DETAIL DE VOS MOUVEMENTS SEPA
VOTRE COMPTE CHEQUES N° 12345 678901 RELEVE N° 8 AU 30/04/2026
DATE DETAIL DE VOS PRELEVEMENTS SEPA RECUS DEBIT
01/04 FOURNISSEUR TEST ALPHA FR76ABCDE12345                 1 380,00 €
2026040100000TESTSYNTH01 144-1
Paiement de la facture Telepaiement du 01/04/2026 RESIDENCE TEST 01
01/04 DIRECTION GENERALE DES FINANCES                        124,00 €
2026040200000TESTSYNTH02 144-1
Paiement de la facture Telepaiement TF 2026
"""


def test_sepa_detail_overrides_sign(monkeypatch):
    """SEPA detail section should override amounts (and sign) for SEPA transactions.

    Transactions that appear as credits (+ sign) in the main table
    but are actually debits should be corrected via the SEPA detail
    section where amounts are always debits.
    """
    monkeypatch.setattr(
        pdfbanquepopulaire,
        "pdf_to_text",
        lambda _: SYNTHETIC_SEPA_DETAIL_SECTION,
    )
    importer = pdfbanquepopulaire.PDFBanquePopulaire(ACCOUNTLIST)

    entries = importer.extract("statement.pdf")
    transactions = [
        entry for entry in entries if isinstance(entry, data.Transaction)
    ]

    assert len(transactions) == 3

    # Transaction 0: FOURNISSEUR TEST — SEPA detail overrides to -1380.00
    assert transactions[0].payee == "PRLV SEPA FOURNISSEUR TEST"
    assert transactions[0].postings[0].units.number == Decimal("-1380.00")

    # Transaction 1: DIRECTION GENE — SEPA detail overrides to -124.00
    assert transactions[1].payee == "PRLV SEPA DIRECTION GENE"
    assert transactions[1].postings[0].units.number == Decimal("-124.00")

    # Transaction 2: COTIS FAMILLE — not a SEPA transaction,
    # no SEPA detail override, keeps its original +12.45
    assert transactions[2].payee == "COTIS FAMILLE CONFORT"
    assert transactions[2].postings[0].units.number == Decimal("12.45")
