import pytest
import subprocess
from myutils import is_pdfminer_installed, pdf_to_text, traduire_mois, TRADUCTIONS_MOIS

"""
Tests pour le module myutils.py.

Ce fichier contient des tests unitaires pour les fonctions du module myutils.py,
utilisant le framework pytest.

Classes de test:
    TestIsPdfminerInstalled: Tests pour la fonction is_pdfminer_installed
    TestPdfToText: Tests pour la fonction pdf_to_text
    TestTraduireMois: Tests pour la fonction traduire_mois
"""

class TestIsPdfminerInstalled:
    """
    Tests pour la fonction is_pdfminer_installed.
    """

    def test_pdfminer_installed(self, monkeypatch):
        """
        Teste le cas où pdfminer est installé.

        Args:
            monkeypatch: Fixture pytest pour modifier temporairement le comportement.
        """
        def mock_run(*args, **kwargs):
            return subprocess.CompletedProcess(args=args, returncode=0)
        
        monkeypatch.setattr(subprocess, "run", mock_run)
        assert is_pdfminer_installed() == True

    def test_pdfminer_not_installed(self, monkeypatch):
        """
        Teste le cas où pdfminer n'est pas installé.

        Args:
            monkeypatch: Fixture pytest pour modifier temporairement le comportement.
        """
        def mock_run(*args, **kwargs):
            raise FileNotFoundError()
        
        monkeypatch.setattr(subprocess, "run", mock_run)
        assert is_pdfminer_installed() == False

class TestPdfToText:
    """
    Tests pour la fonction pdf_to_text.
    """

    def test_successful_conversion(self, monkeypatch):
        """
        Teste une conversion PDF réussie.

        Args:
            monkeypatch: Fixture pytest pour modifier temporairement le comportement.
        """
        def mock_run(*args, **kwargs):
            return subprocess.CompletedProcess(args=args, returncode=0, stdout="Texte converti")
        
        monkeypatch.setattr(subprocess, "run", mock_run)
        assert pdf_to_text("test.pdf") == "Texte converti"

    def test_failed_conversion(self, monkeypatch):
        """
        Teste une conversion PDF échouée.

        Args:
            monkeypatch: Fixture pytest pour modifier temporairement le comportement.
        """
        def mock_run(*args, **kwargs):
            raise subprocess.CalledProcessError(1, args, stderr="Erreur de conversion")
        
        monkeypatch.setattr(subprocess, "run", mock_run)
        with pytest.raises(ValueError, match="Erreur lors de la conversion du PDF : Erreur de conversion"):
            pdf_to_text("test.pdf")

class TestTraduireMois:
    """
    Tests pour la fonction traduire_mois.
    """

    @pytest.mark.parametrize("input_str, expected_output", [
        ("fév", "feb"),
        ("mars", "mar"),
        ("avr", "apr"),
        ("mai", "may"),
        ("juin", "jun"),
        ("juil", "jul"),
        ("août", "aug"),
        ("déc", "dec"),
        ("janvier fév mars", "janvier feb mar"),
        ("Le 15 juin 2023", "Le 15 jun 2023"),
    ])
    def test_traduire_mois(self, input_str, expected_output):
        """
        Teste la traduction des abréviations de mois.

        Args:
            input_str (str): Chaîne d'entrée contenant des abréviations de mois en français.
            expected_output (str): Chaîne de sortie attendue avec les abréviations traduites.
        """
        assert traduire_mois(input_str) == expected_output

    def test_no_translation_needed(self):
        """
        Teste le cas où aucune traduction n'est nécessaire.
        """
        input_str = "Ceci est une phrase sans mois"
        assert traduire_mois(input_str) == input_str

    def test_all_translations(self):
        """
        Teste que toutes les traductions définies sont correctement appliquées.
        """
        input_str = " ".join(TRADUCTIONS_MOIS.keys())
        expected_output = " ".join(TRADUCTIONS_MOIS.values())
        assert traduire_mois(input_str) == expected_output
