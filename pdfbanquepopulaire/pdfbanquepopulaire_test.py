import datetime as dt
from decimal import Decimal

from beancount.core import data

from . import pdfbanquepopulaire


ACCOUNTLIST = {
    "12345678901": "Actif:BanquePopulaire:CCAnna",
    "36319151452": "Actif:BPop:CCTim",
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
                    0059723              27/03                 27/03                          - 136,30 €
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
    assert importer.account("statement.pdf") == "Actif:BanquePopulaire:CCAnna"
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
DETAIL DES OPERATIONS DE VOTRE COMPTE CHEQUES N° 36319151452

SOLDE CREDITEUR AU 07/03/2026                                                                                     0,00 €
28/03             COTIS VISA PREMIER DD
                    XCGFC005 2026032700059725000001
                    CONTRAT CARTE ********788J
                    0059725              27/03                 27/03                          - 136,30 €

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

    assert importer.account("statement.pdf") == "Actif:BPop:CCTim"

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
        == "XCGFC005 2026032700059725000001 CONTRAT CARTE ********788J"
    )
    assert [posting.account for posting in transactions[0].postings] == [
        "Actif:BPop:CCTim",
        "Depenses:Banque:Frais",
    ]
    assert transactions[0].postings[0].units.number == Decimal("-136.30")
    assert transactions[0].postings[1].units is None


SYNTHETIC_BP_CCSCI_STATEMENT = """BANQUE POPULAIRE
Votre relevé de compte n°3 au 31/03/2026
DETAIL DES OPERATIONS DE VOTRE COMPTE COURANT N° 76321119905

SOLDE CREDITEUR AU 27/02/2026                                                                                 31 000,00 €
02/03             PRLV SEPA In Extenso Cen                                                                 05G1U1S              02/03                 02/03                         - 1 380,00 €
                    MFA0577356
                    643393-B13-001
18/03             EVI ME MARTIAL FAUCHER C                                                                 SK3RTPF              18/03                 18/03                            480,00 €
                    MF PAYE SCI LES RAGONDINS 79 DIS
                    PO S/PROV FRAIS VTE SCI AUGUSTA

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
        {**ACCOUNTLIST, "76321119905": "Actif:SCIRagondins:CCSCI"}
    )

    assert importer.identify("statement.pdf")
    assert importer.account("statement.pdf") == "Actif:SCIRagondins:CCSCI"
    assert importer.date("statement.pdf") == dt.date(2026, 3, 31)


SYNTHETIC_BP_CCSCI_WITH_SEPA_SECTION = """BANQUE POPULAIRE
Votre relevé de compte n°3 au 31/03/2026
DETAIL DES OPERATIONS DE VOTRE COMPTE COURANT N° 76321119905

SOLDE CREDITEUR AU 27/02/2026                                                                                 31 000,00 €
02/03             PRLV SEPA In Extenso Cen                                                                 05G1U1S              02/03                 02/03                         - 1 380,00 €
                    MFA0577356
                    643393-B13-001
18/03             EVI ME MARTIAL FAUCHER C                                                                 SK3RTPF              18/03                 18/03                            480,00 €
                    MF PAYE SCI LES RAGONDINS 79 DIS
                    PO S/PROV FRAIS VTE SCI AUGUSTA

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
        {**ACCOUNTLIST, "76321119905": "Actif:SCIRagondins:CCSCI"}
    )

    entries = importer.extract("statement.pdf")
    transactions = [
        entry for entry in entries if isinstance(entry, data.Transaction)
    ]

    assert len(transactions) == 2
    assert transactions[0].payee == "PRLV SEPA In Extenso Cen"
    assert transactions[1].payee == "EVI ME MARTIAL FAUCHER C"


SYNTHETIC_BP_CCSCI_OCR_CORRUPTED_STATEMENT = """BANQUE POPULAIRE
Votre relevé de compte n°4 au 30/04/2026
DETAIL DES OPERATIONS DE VOTRE COMPTE COURANT N° 76321119905

SOLDE CREDITEUR AU 31/03/2026                                                                                  7 714,94 €
07/04               ARRETE DE CPTE                                                                     1151121                07/04                    31/03                                 -6175€
                      1 ER TRIMESTRE 2026
08/04                PRLV SEPA 0035 SDC CENT                                                           OSPWATY                07/04                   07/04                            73 639.47 €
                      Paiement de la facture Telepaiem
                      202603280000000141101T01669
09/04                ECHEANCE PRET                                                                     9185489                07/04                   06/04                                 - 249,08 €
                      DONT CAP           0,00 ASS.      0,00E
                      INT,   249,08 COM.         0,00E
10/04                FRAIS MANDAT PRLV SEPA                                                            0063904                09/04                   09/04                                   - 1,00 €
                     XCIMRO10 2026040900063904000001
                      CREANCIER            0035 SDC CENTRE

                                S DEBITEURS
TOTAL DES MOUVEMENTS CREDITEURS                                                                                                                                                0,00 €

SOLDE CREDITEUR AU 30/04/2026*
(*) Sous réserve des opérations en cours d'enregistrement et d'une provision suffisante et disponible lors de l'arrêté du solde du compte réalisé en fin de journée.
Ce document ne justifie pas la déduction de la TVA ou de la charge en matière d'impôt direct.

DETAIL DE VOS MOUVEMENTS SEPA
VOTRE COMPTE COURANT N° 76321 119905 RELEVE N° 4 AU 30/04/2026
DATE DETAIL DE VOS PRELEVEMENTS SEPA RECUS DEBIT
07/04 0035 SDC CENTRE LEO LAGRANGE FR93277Z82FAF4 3 639,47 €
202603280000000141101T01669 144-1
Paiement de la facture Telepaiement du 01/04/2026 LES RAGONDINS 79
"""


def test_extract_current_account_with_ocr_corrupted_amounts(monkeypatch):
    monkeypatch.setattr(
        pdfbanquepopulaire,
        "pdf_to_text",
        lambda _: SYNTHETIC_BP_CCSCI_OCR_CORRUPTED_STATEMENT,
    )
    importer = pdfbanquepopulaire.PDFBanquePopulaire(
        {**ACCOUNTLIST, "76321119905": "Actif:SCIRagondins:CCSCI"}
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
    assert transactions[1].payee == "PRLV SEPA 0035 SDC CENT"
    assert "202603280000000141101T01669" in transactions[1].narration
