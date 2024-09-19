"""Unit tests for pdfamex importer (using pytest)."""

__copyright__ = (
    "Copyright (C) 2018  Martin Blais - slightly modified by Grostim"
)
__license__ = "GNU GPLv2"

from os import path
import pytest

from beancount.ingest import regression_pytest as regtest
from . import pdfamex

ACCOUNTLIST = {
    "xxxx-xxxxxx-72001": "Passif:AirFrance:Amex",
}

IMPORTER = pdfamex.PDFAmex(ACCOUNTLIST)


@regtest.with_importer(IMPORTER)
@regtest.with_testdir(
    path.abspath("regtest/Beancount-myTools-tests/pdfamex/")
)
class TestImporter(regtest.ImporterTestBase):
    pass
