# Beancount-myTools
Ma boite à outils Beancount: Les scripts sont  destinés aux banques francaises.

Certains de ces scripts ont des dépendances.
Toutes ces dépendances sont inclues dans le docker que j'ai créé pour l'occasion:
https://github.com/grostim/fava-docker
Mais rien n'empèche d'utiliser ces scripts hors Docker.

Les fichiers de regtest ne sont pas partagés sur github, car bien entendu ce sont des fichiers personnels.

Tous ces poutils sont très perfectibles, n'hésitez pas à me faire part de vos propositions d'améliorations, ou mieux encore une pull request.

## QIFBoursorama
Un importer pour les fichiers QIF générés par Boursorama.
Je recommandecependant d'importer les pdfs avec PDFbourso : (plus de détails et récupération des balance).

## PDFBourso
Un importer pour les relevés au format PDF emis par Boursorama.
Testé avec:
- les relevés de compte courant
- les relevés de LDD et CEL
- Les relevés de carte à débit différé.
Il n'a pas été testé avec les autres types de comptes.

## PDFAmex

### Présentation générale
Un importateur avancé pour les relevés au format PDF émis par American Express. Cet outil extrait les transactions et le solde des relevés, les convertit en directives Beancount, et gère efficacement les spécificités des relevés American Express, y compris les dates de transaction dans le futur et les différents types de transactions.

### Utilisation
1. Assurez-vous d'avoir les dépendances nécessaires installées (beancount, dateutil, etc.).
2. Configurez le dictionnaire `account_list` dans votre fichier de configuration Beancount pour faire correspondre les numéros de compte American Express à vos comptes Beancount.
3. Ajoutez l'importateur à votre configuration Beancount :
   ```python
   from pdfamex import PDFAmex
   CONFIG = [
       PDFAmex(account_list={
           "12345": "Liabilities:CreditCard:Amex",
           # Ajoutez d'autres comptes si nécessaire
       }),
   ]
   ```
4. Utilisez l'importateur avec les commandes habituelles de Beancount (bean-extract, bean-identify, etc.).

### Limitations
- Principalement testé avec les cartes Amex / Air France KLM. Bien qu'il devrait fonctionner pour d'autres types de cartes American Express, des ajustements peuvent être nécessaires pour certains formats spécifiques.
- Ne gère pas automatiquement les transactions en devises étrangères. Les montants sont supposés être en euros.
- L'extraction du solde total suppose un format spécifique dans le relevé. Des modifications peuvent être nécessaires pour des formats de relevés différents.
- La détection des transactions de crédit se base sur la présence d'un indicateur "CR". Cela pourrait nécessiter des ajustements pour certains types de relevés.

## generali.py
Un script qui récupère tout l'historique d'une assurance e-cie Vie (Generali) et les sauvegardes sous formes de fichiers JSON.
A ce stade, il n'a été testé que sur un contrat commercialisé par Linxea.

## JSONGenerali
Un importer pour les relevés au format JSON généré par le script précédent.

## PDFBinck
Un importer pour les relevés au format PDF emis par Binck France.
A ce stade, cet importer se contente de classer le fichier.

## IEXCloud
Un price fetcher qui utilise iexcloud.io.
Une clef API est requise (gratuite pour un usage limité)

## AMFGeco
un price fetcher pour FCP et sicav FR qui utilise la base AMF Geco

## Quantalys
un price fetcher pour FCP et sicav FR qui utilise la base Quantalys. Ce price fetcher ne peut pas récupérer les historiques.

## Cryptocompare
un price fetcher pour les cryptosmonnaies.

## Realt
un price fetcher pour les Realtokens - basé sur l'API du site communautaire.

## fichepaye.py
Un importateur avancé pour les fiches de paie au format PDF émises par Sage ou DUO_TEC. Cet outil extrait les informations clés des fiches de paie, telles que la date de paiement, le net avant impôt, l'impôt sur le revenu et le net à payer, puis les convertit en directives Beancount. Il gère efficacement l'extraction des données et la création de transactions Beancount correspondantes.

### Utilisation
1. Assurez-vous d'avoir les dépendances nécessaires installées (beancount, dateutil, pdfminer, etc.).
2. Configurez le dictionnaire `account_list` dans votre fichier de configuration Beancount pour faire correspondre les numéros de compte aux comptes Beancount appropriés.
3. Ajoutez l'importateur à votre configuration Beancount :
   ```python
   from fichepaye import FichePaye
   CONFIG = [
       FichePaye(
           account_list={
               "02568047100015": "Revenus:Salaire:Entreprise",
               # Ajoutez d'autres comptes si nécessaire
           },
           compteCourant="Actif:Banque:CompteCourant",
           compteImpot="Depenses:Impots:RevenuSource",
           payee="NomEmployeur"
       ),
   ]
   ```
4. Utilisez l'importateur avec les commandes habituelles de Beancount (bean-extract, bean-identify, etc.).

### Fonctionnalités
- Extraction automatique des informations clés de la fiche de paie.
- Création de transactions Beancount avec les montants appropriés.
- Gestion des comptes pour le salaire, l'impôt sur le revenu et le compte courant.
- Mode debug pour faciliter le dépannage.

### Limitations
- Spécifiquement conçu pour les fiches de paie émises par Sage ou DUO_TEC. Des modifications seront nécessaires pour d'autres formats.
- L'extraction des montants se base sur des motifs regex spécifiques qui pourraient nécessiter des mises à jour en cas de changement de format des fiches de paie.
- Ne gère pas l'importation détaillée de toutes les lignes de la fiche de paie, se concentrant sur les montants principaux (net avant impôt, impôt sur le revenu, net à payer).
- Suppose que les montants sont en euros. Des ajustements seraient nécessaires pour d'autres devises.


## myutils.py

Le module `myutils.py` contient diverses fonctions utilitaires communes aux importateurs. Voici un aperçu des principales fonctionnalités :

### Fonctions

#### `is_pdfminer_installed()`
- Vérifie si la commande `pdftotext` est disponible sur le système.
- Retourne `True` si `pdftotext` est installé, `False` sinon.

#### `pdf_to_text(filename: str)`
- Convertit un fichier PDF en texte.
- Paramètres :
  - `filename` (str) : Chemin du fichier PDF à convertir.
- Retourne le contenu textuel du fichier PDF.
- Lève une `ValueError` si la conversion échoue.

#### `traduire_mois(mois: str)`
- Traduit les abréviations de mois du français vers l'anglais.
- Paramètres :
  - `mois` (str) : Chaîne contenant des abréviations de mois en français.
- Retourne la chaîne avec les abréviations de mois traduites en anglais.

### Utilisation

Ce module est particulièrement utile pour les importateurs qui nécessitent la manipulation de fichiers PDF et la traduction de dates. Il simplifie les tâches courantes telles que la vérification de l'installation de `pdftotext`, la conversion de PDF en texte, et la normalisation des abréviations de mois pour le traitement des dates.

### Dépendances

- Le module utilise la bibliothèque standard Python `subprocess` pour exécuter des commandes système.
- La fonction `pdf_to_text()` nécessite que `pdftotext` soit installé sur le système.

### Remarques

- Les fonctions sont conçues pour être réutilisables dans différents contextes d'importation.
- Le module inclut des gestions d'erreurs appropriées, notamment pour les cas où `pdftotext` n'est pas installé ou échoue lors de la conversion.
- La traduction des mois est particulièrement utile pour normaliser les dates extraites de documents en français vers un format compatible avec les bibliothèques de traitement de dates en anglais.

