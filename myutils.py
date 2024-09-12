"""
Diverses fonctions utiles communes à mes importers.

Ce module contient des fonctions utilitaires pour la manipulation de fichiers PDF,
la vérification de l'installation de pdfminer, et la traduction des abréviations de mois.

Functions:
    is_pdfminer_installed(): Vérifie si pdftotext est installé.
    pdf_to_text(filename: str): Convertit un fichier PDF en texte.
    traduire_mois(mois: str): Traduit les abréviations de mois du français vers l'anglais.
"""

__copyright__ = "Copyright (C) 2019 Grostim"
__license__ = "GNU GPLv2"

import subprocess
from typing import Dict


def is_pdfminer_installed() -> bool:
    """
    Vérifie si la commande pdftotext est disponible sur le système.

    Returns:
        bool: True si pdftotext est installé, False sinon.
    """
    try:
        result = subprocess.run(["pdftotext", "-v"], capture_output=True, text=True, check=False)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def pdf_to_text(filename: str) -> str:
    """
    Convertit un fichier PDF en texte.

    Args:
        filename (str): Chemin du fichier à convertir

    Returns:
        str: Contenu textuel du fichier PDF.

    Raises:
        ValueError: Si la conversion échoue.
    """
    try:
        result = subprocess.run(["pdftotext", "-layout", filename, "-"], 
                                capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Erreur lors de la conversion du PDF : {e.stderr}")


TRADUCTIONS_MOIS = {
    "fév": "feb", "mars": "mar", "avr": "apr", "mai": "may",
    "juin": "jun", "juil": "jul", "août": "aug", "déc": "dec"
}

def traduire_mois(mois: str) -> str:
    """
    Traduit les abréviations de mois du français vers l'anglais.

    Args:
        mois (str): Chaîne contenant des abréviations de mois en français.

    Returns:
        str: Chaîne avec les abréviations de mois traduites en anglais.
    """
    for fr, en in TRADUCTIONS_MOIS.items():
        mois = mois.replace(fr, en)
    return mois