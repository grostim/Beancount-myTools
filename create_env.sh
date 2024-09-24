#!/bin/bash

# Vérifier si virtualenv est installé, sinon l'installer
if ! command -v virtualenv &> /dev/null
then
    echo "virtualenv n'est pas installé. Installation en cours..."
    pip install virtualenv
    if [ $? -ne 0 ]; then
        echo "Échec de l'installation de virtualenv."
        exit 1
    fi
fi

# Créer un environnement virtuel nommé 'venv'
echo "Création de l'environnement virtuel 'venv'..."
virtualenv venv
if [ $? -ne 0 ]; then
    echo "Échec de la création de l'environnement virtuel."
    exit 1
fi

# Activer l'environnement virtuel
echo "Activation de l'environnement virtuel..."
if [[ "$OSTYPE" == "msys" ]]; then
    .\venv\Scripts\activate
else
    source venv/bin/activate
fi
if [ $? -ne 0 ]; then
    echo "Échec de l'activation de l'environnement virtuel."
    exit 1
fi

# Installer les dépendances depuis requirements.txt
echo "Installation des dépendances depuis requirements.txt..."
apt-get install libpoppler-cpp-dev
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Échec de l'installation des dépendances."
    exit 1
fi

