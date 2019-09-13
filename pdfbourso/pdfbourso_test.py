"""Unit tests for pdfamex importer (using pytest)."""
__copyright__ = "Copyright (C) 2018  Martin Blais - slightly modified by Grostim"
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
    "10014935408": "Passif:Boursorama:CBTim",
    "4979********1974": "Passif:Boursorama:CBTim",
    "xxxx-xxxxxx-72001": "Passif:AirFrance:Amex",
    "00030305440": "Actif:Boursorama:CELAnna",
    "00031305390": "Actif:Boursorama:PELAnna",
    "00020871896": "Actif:Boursorama:LDDAnna",
    "00020132893": "Actif:Boursorama:LDDAnna"
}

IMPORTER = pdfbourso.pdfbourso(ACCOUNTLIST)


@regtest.with_importer(IMPORTER)
@regtest.with_testdir("/myData/myTools/pdfbourso/regtest")
class TestImporter(regtest.ImporterTestBase):
    pass
