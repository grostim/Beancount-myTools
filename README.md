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

## fichepaye
Un importer pour les bulletins de paye (pdf) de mon employeur. Ceux ci sont édités avec Sage.
Il est peut probable que le script soit directement utilisable par un salarié d'une autre entreprise (d'autant plus que certains comptes sont en dur dans le code python), mais celà peut servir de base d'inspiration à d'autres personne.
