"""Unit tests for pdfamex importer (using pytest)."""
__copyright__ = (
    "Copyright (C) 2018  Martin Blais - slightly modified by Grostim"
)
__license__ = "GNU GPLv2"

from os import path
import pytest

from beancount.ingest import regression_pytest as regtest
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


@regtest.with_importer(IMPORTER)
@regtest.with_testdir(
    path.abspath("regtest/Beancount-myTools-tests/pdfbourso/")
)
class TestImporter(regtest.ImporterTestBase):
    pass
