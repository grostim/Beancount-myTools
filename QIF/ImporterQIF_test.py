"""Unit tests for QIF importer (using pytest)."""
__copyright__ = "Copyright (C) 2018  Martin Blais - slightly modified by Grostim"
__license__ = "GNU GPLv2"

from os import path
import pytest

from beancount.ingest import regression_pytest as regtest
from . import ImporterQIF

ACCOUNTLIST = {
    "00040754305": "Actif:Boursorama:CCJoint",
}
IMPORTER = ImporterQIF.ImporterQIF(ACCOUNTLIST)


@regtest.with_importer(IMPORTER)
@regtest.with_testdir("/myData/myTools/QIF/regtest")
class TestImporter(regtest.ImporterTestBase):
    pass
