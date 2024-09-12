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


def traduire_mois(mois: str) -> str:
    """
    Traduit les abréviations de mois du français vers l'anglais.
    
    Args:
        mois (str): Abréviation du mois en français
    
    Returns:
        str: Abréviation du mois en anglais
    
    Raises:
        ValueError: Si l'abréviation du mois n'est pas reconnue
    """
    traductions: Dict[str, str] = {
        'jan': 'jan', 'fév': 'feb', 'mar': 'mar', 'avr': 'apr',
        'mai': 'may', 'jui': 'jun', 'jul': 'jul', 'aoû': 'aug',
        'sep': 'sep', 'oct': 'oct', 'nov': 'nov', 'déc': 'dec'
    }
    mois_lower = mois.lower()
    if mois_lower not in traductions:
        raise ValueError(f"Mois non reconnu : {mois}")
    return traductions[mois_lower]
