"""
Configuration pytest pour les tests de régression Beancount.

Ce fichier importe le plugin de régression pytest de Beancount,
qui ajoute l'option --generate aux tests.
"""

# This adds the --generate option.
# pylint: disable=invalid-name
pytest_plugins = "beancount.ingest.regression_pytest"
