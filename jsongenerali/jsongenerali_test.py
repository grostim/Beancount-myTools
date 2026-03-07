"""Unit tests for jsongenerali importer (using pytest)."""
__copyright__ = (
    "Copyright (C) 2018  Martin Blais - slightly modified by Grostim"
)
__license__ = "GNU GPLv2"

import os
from os import path
import pytest

from beangulp.testing import compare_expected, run_importer
from . import jsongenerali

ACCOUNTLIST = {
    "P54112927": "Actif:Linxea:AVTim1",
}

IMPORTER = jsongenerali.JSONGenerali(ACCOUNTLIST)

TESTDIR = path.abspath("regtest/Beancount-myTools-tests/jsongenerali/")

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
