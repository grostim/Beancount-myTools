"""Unit tests for QIF importer (using pytest)."""
__copyright__ = "Copyright (C) 2018  Martin Blais - slightly modified by Grostim"
__license__ = "GNU GPLv2"

from os import path
import pytest

from beancount.ingest import regression_pytest as regtest
from . import ImporterQIF


IMPORTER = ImporterQIF()

@regtest.with_importer(IMPORTER)
@regtest.with_testdir("./regtest")
class TestImporter(regtest.ImporterTestBase):
    pass

