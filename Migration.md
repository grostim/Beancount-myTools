# Guide de Migration : De `beancount.ingest` vers `beangulp`

Ce guide est destiné aux développeurs souhaitant mettre à jour leurs importateurs Beancount pour utiliser la nouvelle bibliothèque `beangulp`. Cette migration est nécessaire pour assurer la compatibilité avec les futures versions de Beancount (v3).

## Pourquoi migrer ?

L'ancien module `beancount.ingest` est remplacé par `beangulp`. `beangulp` est plus léger et sépare clairement la logique d'importation du cœur de Beancount.

## Prérequis

Avant de commencer, assurez-vous d'avoir installé `beangulp` :

```bash
pip install beangulp
```

Et ajoutez-le à votre fichier `requirements.txt` ou `pyproject.toml`.

## Étapes de Migration

Voici les étapes pas à pas pour transformer votre ancien importateur.

### 1. Mettre à jour les imports

Remplacez l'import de `beancount.ingest` par `beangulp`.

**Avant :**
```python
from beancount.ingest import importer
```

**Après :**
```python
import beangulp
```

### 2. Changer la classe parente

Votre classe d'importateur doit maintenant hériter de `beangulp.Importer`.

**Avant :**
```python
class MonImporter(importer.ImporterProtocol):
```

**Après :**
```python
class MonImporter(beangulp.Importer):
```

### 3. Renommer les méthodes

`beangulp` utilise des noms de méthodes légèrement différents (plus courts). Vous devez renommer les méthodes suivantes :

| Ancien nom (`beancount.ingest`) | Nouveau nom (`beangulp`) |
| ------------------------------- | ------------------------ |
| `file_name(self, file)`         | `filename(self, file)`   |
| `file_account(self, file)`      | `account(self, file)`    |
| `file_date(self, file)`         | `date(self, file)`       |

### 4. Gérer les fichiers comme des chaînes de caractères (Important !)

C'est le changement le plus important.
*   **Avant** : `file` était un objet spécial avec des méthodes comme `file.name`, `file.mimetype()`, et `file.convert()`.
*   **Après** : `file` est simplement une **chaîne de caractères** (le chemin vers le fichier, ex: `/path/to/file.pdf`).

Il faut donc adapter votre code :

#### a. Identification (`identify`)

Ne vérifiez plus le mimetype via `file.mimetype()`. Vérifiez l'extension du fichier directement.

**Avant :**
```python
def identify(self, file):
    return file.mimetype() == "application/pdf"
```

**Après :**
```python
def identify(self, file):
    return file.lower().endswith(".pdf")
```

#### b. Conversion de PDF en texte

N'utilisez plus `file.convert()`. Utilisez une fonction utilitaire externe (comme `pdf_to_text` dans `myutils.py`) qui prend le chemin du fichier en argument.

**Avant :**
```python
text = file.convert(pdf_to_text)
```

**Après :**
```python
# Assurez-vous d'avoir importé votre fonction utilitaire
text = pdf_to_text(file)
```

#### c. Accès au nom du fichier

Si vous utilisiez `file.name` pour obtenir le chemin, utilisez simplement `file` directement.

**Avant :**
```python
meta = data.new_metadata(file.name, 0)
basename = os.path.basename(file.name)
```

**Après :**
```python
meta = data.new_metadata(file, 0)
basename = os.path.basename(file)
```

#### d. Ouverture de fichiers (pour JSON, CSV, etc.)

Si vous ouvriez le fichier, utilisez le chemin directement.

**Avant :**
```python
with open(file.name) as f:
```

**Après :**
```python
with open(file) as f:
```

### 5. Exemple complet

Voici un résumé visuel d'une migration typique.

**Code Original (`beancount.ingest`) :**

```python
from beancount.ingest import importer
from myutils import pdf_to_text

class MonImporter(importer.ImporterProtocol):
    def identify(self, file):
        return file.mimetype() == "application/pdf"

    def file_account(self, file):
        return "Assets:Bank"

    def extract(self, file, existing_entries=None):
        text = file.convert(pdf_to_text)
        # ... logique d'extraction ...
        meta = data.new_metadata(file.name, 0)
        # ...
```

**Code Migré (`beangulp`) :**

```python
import beangulp
from myutils import pdf_to_text

class MonImporter(beangulp.Importer):
    def identify(self, file):
        return file.lower().endswith(".pdf")

    def account(self, file):
        return "Assets:Bank"

    def extract(self, file, existing_entries=None):
        text = pdf_to_text(file) # file est un str
        # ... logique d'extraction ...
        meta = data.new_metadata(file, 0) # file est un str
        # ...
```

## Vérification

Après la migration, il est conseillé de tester votre importateur :
1.  Instanciez votre classe.
2.  Appelez `identify("chemin/vers/test.pdf")`.
3.  Appelez `extract("chemin/vers/test.pdf")`.

Si vous rencontrez des erreurs comme `AttributeError: 'str' object has no attribute 'mimetype'` ou `no attribute 'convert'`, c'est que vous avez oublié de mettre à jour une utilisation de l'objet `file`.
