"""Unit tests for pdfamex importer (using pytest)."""
__copyright__ = (
    "Copyright (C) 2018  Martin Blais - slightly modified by Grostim"
)
__license__ = "GNU GPLv2"

import os
from os import path
from decimal import Decimal
import pytest

from beancount.core import data
from beangulp.testing import compare_expected, run_importer
from . import pdfbourso

ACCOUNTLIST = {
    "00040754305": "Actif:Boursorama:CCJoint",
    "00040132901": "Actif:Boursorama:CCTim",
    "00040239557": "Actif:Boursorama:CCAnna",
    "10014570396": "Passif:Boursorama:CBJoint",
    "4979********1979": "Passif:Boursorama:CBJoint",
    "4810********2934": "Passif:Boursorama:CBJoint",
    "10014935408": "Passif:Boursorama:CBTim",
    "4979********1974": "Passif:Boursorama:CBTim",
    "4979********6048": "Passif:Boursorama:CBTim",
    "4810********2766": "Passif:Boursorama:CBTim",
    "00030305440": "Actif:Boursorama:CELAnna",
    "00031305390": "Actif:Boursorama:PELAnna",
    "00020871896": "Actif:Boursorama:LDDAnna",
    "00030269844": "Actif:Boursorama:CELTim",
    "00020132893": "Actif:Boursorama:LDDJoint",
    "80329 - 00060818936": "Passif:Boursorama:PretConso",
    "80366 - 00060273227": "Passif:Boursorama:PretMitsu",
    "80280-00060686223": "Passif:Boursorama:EmpruntRP",
    "00088339677": "Actif:Boursorama:PEA",
    "00090339677": "Actif:Boursorama:PEA",
    "00050340253": "Actif:Boursorama:CTO",
    "00080340253": "Actif:Boursorama:CTO"
}

IMPORTER = pdfbourso.PDFBourso(ACCOUNTLIST, debug=True)

TESTDIR = path.abspath("regtest/Beancount-myTools-tests/pdfbourso/")

def get_test_files():
    if not path.isdir(TESTDIR):
        return []
    files = []
    for f in os.listdir(TESTDIR):
        if not f.endswith('.beancount'):
            expected = path.join(TESTDIR, f + '.beancount')
            if path.exists(expected):
                files.append(path.join(TESTDIR, f))
    return files

@pytest.mark.parametrize("doc", get_test_files())
def test_importer(doc):
    assert IMPORTER.identify(doc)
    account, date, name, entries = run_importer(IMPORTER, doc)
    expected_filename = doc + ".beancount"
    
    diff = compare_expected(expected_filename, account, date, name, entries)
    assert not diff, "Diff found:\n" + "".join(diff)


def test_extract_compte_cel_layout_uses_credit_column(monkeypatch):
    text = """BOURSORAMA BANQUE
Relevé au 30/05/2025
Compte 00030269844
Date opération                                 Libellé                                      Valeur                   Débit                    Crédit
                                                         SOLDE EN EUR        AU :         01/02/2025                                                319,11
  30/05/2025        VIR Virement interne depuis COMPTE P                                  30/05/2025                                              3.000,00
                                                Nouveau solde en EUR                           1                                                  3.319,11
"""
    monkeypatch.setattr(pdfbourso, "pdf_to_text", lambda _: text)
    importer = pdfbourso.PDFBourso(ACCOUNTLIST, debug=True)

    entries = importer._extract_compte("fake.pdf", text, "2025-05-30 Relevé Compte.pdf")

    balances = [entry for entry in entries if isinstance(entry, data.Balance)]
    transactions = [entry for entry in entries if isinstance(entry, data.Transaction)]

    assert [entry.amount.number for entry in balances] == [Decimal("319.11"), Decimal("3319.11")]
    assert transactions[0].postings[0].units.number == Decimal("3000.00")


def test_extract_compte_regular_layout_keeps_debit_negative(monkeypatch):
    text = """BOURSORAMA BANQUE
Relevé au 28/02/2026
Compte 00040132901
          Libellé                                                                                              Valeur              Débit                Crédit
                                                                                             SOLDE AU : 30/01/2026                                          4.783,72
05/02/2026 PRLV SEPA Free Telecom                                                                            05/02/2026                  37,97
                                Nouveau solde en EUR :                                                                                                     3.104,54
"""
    monkeypatch.setattr(pdfbourso, "pdf_to_text", lambda _: text)
    importer = pdfbourso.PDFBourso(ACCOUNTLIST, debug=True)

    entries = importer._extract_compte("fake.pdf", text, "2026-02-28 Relevé Compte.pdf")

    balances = [entry for entry in entries if isinstance(entry, data.Balance)]
    transactions = [entry for entry in entries if isinstance(entry, data.Transaction)]

    assert [entry.amount.number for entry in balances] == [Decimal("4783.72"), Decimal("3104.54")]
    assert transactions[0].postings[0].units.number == Decimal("-37.97")


def test_extract_espece_bourse_uses_debit_credit_columns_for_balance_sign(monkeypatch):
    text = """BoursoBank
RELEVE COMPTE ESPECES: FEVRIER 2025
RIB du compte espèces : 40618 80295 00090339677 54
Références de votre compte espèces
40618 80295 00090339677
Date de
 compta.                           Libellé de l'opération                             Quantité             Nom de la valeur            Débit EUR                                            Crédit EUR
 31/01/2025                                                                        ANCIEN SOLDE                                                               720,38
 03/02/2025 RACHAT D'OPC                                                                         -10   AXA PEA REG.C 4DEC                                                                         1 025,91
 13/02/2025 RACHAT D'OPC                                                                         -10   AXA PEA REG.C 4DEC                                                                         1 026,86
 17/02/2025 ACHAT ETRANGER                                                                       200   ISHS VI-ISMWSPE EO                                1 189,78
 28/02/2025                                                                      NOUVEAU SOLDE                                                                                                     142,61
"""
    monkeypatch.setattr(pdfbourso, "pdf_to_text", lambda _: text)
    importer = pdfbourso.PDFBourso(ACCOUNTLIST, debug=True)
    monkeypatch.setattr(importer, "account", lambda _: "Actif:Boursorama:PEA")

    entries = importer._extract_espece_bourse("fake.pdf", text, "2025-02-28 Relevé Espece.pdf")

    balances = [entry for entry in entries if isinstance(entry, data.Balance)]

    assert [entry.date.isoformat() for entry in balances] == ["2025-01-31", "2025-02-28"]
    assert [entry.amount.number for entry in balances] == [Decimal("-720.38"), Decimal("142.61")]


def test_extract_cb_commission_operation_posts_bank_fees(monkeypatch):
    text = """BOURSORAMA BANQUE
Relevé de Carte Premier
Date           N° de RIB                                        N° Carte                    Période                                    Page
 28/03/2026    40618 80268     00040132901              60          4810********2766             du 26/02/2026 au 27/03/2026             1/2
25/03/2026              CARTE 23/03/26 WH Smith Bristo                                                                             19,01
                           16,38 GBP / 1 euro = 0,861651762
25/03/2026              CION OP.ETR WH Smith Bristo                                                                                    0,32
                                       A VOTRE DEBIT LE 01/04/2026                                                                                                        19,33
"""
    monkeypatch.setattr(pdfbourso, "pdf_to_text", lambda _: text)
    importer = pdfbourso.PDFBourso(ACCOUNTLIST, debug=True)

    entries = importer._extract_cb("fake.pdf", text, "2026-03-27 Relevé CB.pdf")

    transactions = [entry for entry in entries if isinstance(entry, data.Transaction)]
    fee_entry = next(entry for entry in transactions if entry.payee == "CION OP.ETR WH Smith Bristo")

    assert fee_entry.date.isoformat() == "2026-03-25"
    assert len(fee_entry.postings) == 2
    assert fee_entry.postings[0].account == "Passif:Boursorama:CBTim"
    assert fee_entry.postings[0].units.number == Decimal("-0.32")
    assert fee_entry.postings[1].account == "Depenses:Banque:Frais"
    assert fee_entry.postings[1].units.number == Decimal("0.32")
