"""Unit tests for pdfamex importer (using pytest)."""

__copyright__ = (
    "Copyright (C) 2018  Martin Blais - slightly modified by Grostim"
)
__license__ = "GNU GPLv2"

from os import path
import pytest

from beancount.ingest import regression_pytest as regtest
from . import fichepaye

ACCOUNTLIST = {
    "025680471 00015": "Revenus:Salaires",
    "02568047100015": "Revenus:Salaires"
}

IMPORTER = fichepaye.FichePaye(ACCOUNTLIST)


@regtest.with_importer(IMPORTER)
@regtest.with_testdir(
    path.abspath("regtest/Beancount-myTools-tests/fichepaye/")
)
class TestImporter(regtest.ImporterTestBase):
    pass
