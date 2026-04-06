import datetime as dt
from decimal import Decimal

from beancount.core import data

from . import pdfbanquepopulaire


ACCOUNTLIST = {
    "12345678901": "Actif:BanquePopulaire:CCAnna",
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

