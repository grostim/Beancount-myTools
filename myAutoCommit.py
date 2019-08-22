"""Auto-commit hook for Fava.

This mainly serves as an example how Fava's extension systems, which only
really does hooks at the moment, works.
"""
# pylint: disable=missing-docstring

import os
import subprocess

from fava.ext import FavaExtensionBase


class AutoCommit(FavaExtensionBase):  # pragma: no cover
    def _run(self, args):
        cwd = os.path.dirname(self.ledger.beancount_file_path)
        subprocess.call(args, cwd=cwd, stdout=subprocess.DEVNULL)

    def after_write_source(self, path, _):
        message = "autocommit by fava: file saved"
        mail=""timothee.gros@gmail.com"
        self._run(["git", "config", "user.email", mail])
        user="Timothée GROS"
        self._run(["git", "config", "user.name", user])
        self._run(["git", "add", path])
        self._run(["git", "commit", "-m", message])
        self._run(["git", "pull"])

    def after_insert_metadata(self, *_):
        mail=""timothee.gros@gmail.com"
        self._run(["git", "config", "user.email", mail])
        user="Timothée GROS"
        self._run(["git", "config", "user.name", user])
        message = "autocommit by fava: metadata added"
        self._run(["git", "commit", "-am", message])
        self._run(["git", "pull"])

    def after_insert_entry(self, entry):
        mail=""timothee.gros@gmail.com"
        self._run(["git", "config", "user.email", mail])
        user="Timothée GROS"
        self._run(["git", "config", "user.name", user])
        message = "autocommit by fava: entry on {}".format(entry.date)
        self._run(["git", "commit", "-am", message])
        self._run(["git", "pull"])
