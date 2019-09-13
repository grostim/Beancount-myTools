# Beancount-myTools
Ma boite à outils Beancount: Les scripts sont  destinés aux banques francaises.

Certains de ces scripts ont des dépendances.
Toutes ces dépendances sont inclues dans le docker que j'ai créé pour l'occasion:
https://github.com/grostim/fava-docker
Mais rien n'empèche d'utiliser ces scripts hors Docker.


## QIFBoursorama 
Un importer pour les fichiers QIF générés par Boursorama.

## PDFBourso
Un importer pour les relevés au format PDF emis par Boursorama.
A ce stade, il fonctionne avec:
- les relevés de compte courant
- les relevés de LDD et CEL
Il ne fonctionne pas avec:
- Les relevés de carte à débit différé.
Il n'a pas été testé avec les autres types de comptes.

## PDFAmex
Un importer pour les relevés au format PDF emis par AmericanExpress
A ce stade, il n'a été testé que pour les cartes Amex / Air France.

## generali.py
Un script qui récupère tout l'historique d'une assurance e-cie Vie (Generali) et les sauvegardes sous formes de fichiers JSON.
A ce stade, il n'a été testé que sur un contrat commercialisé par Linxea.

## JSONGenerali
Un importer pour les relevés au format JSON généré par le script précédent.
WORK-IN-PROGRESS. Non fonctionnel à ce jour.
