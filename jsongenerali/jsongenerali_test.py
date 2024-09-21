"""Unit tests for jsongenerali importer (using pytest)."""
__copyright__ = (
    "Copyright (C) 2018  Martin Blais - slightly modified by Grostim"
)
__license__ = "GNU GPLv2"

from os import path
import pytest

from beancount.ingest import regression_pytest as regtest
from . import jsongenerali

ACCOUNTLIST = {
    "P54112927": "Actif:Linxea:AVTim1",
}

IMPORTER = jsongenerali.jsongenerali(ACCOUNTLIST)


@regtest.with_importer(IMPORTER)
@regtest.with_testdir(
    path.abspath("regtest/Beancount-myTools-tests/jsongenerali/")
)
class TestImporter(regtest.ImporterTestBase):
    pass
