# Filtre d'emails pour OVH

Ce projet contient des scripts Python pour filtrer automatiquement les emails d'une boîte mail OVH, en remplacement des scripts Sieve non disponibles sur le serveur de mail.

## Fonctionnalités

- **Filtrage intelligent** des emails en fonction de :
  - Liste noire (blacklist) des expéditeurs
  - Liste blanche (whitelist) des expéditeurs
  - Indicateurs de spam (mots-clés, scores OVH/SpamAssassin)
  - Détection des newsletters
  - Vérification des adresses destinataires valides

- **Organisation automatique** des emails dans différents dossiers :
  - **Junk** pour les spams
  - **Newsletters** pour les newsletters
  - **Archive** pour les emails spécifiques (comme ceux de Brevo)

- **Gestion des listes** :
  - Ajout automatique aux listes noire/blanche
  - Configuration via fichiers texte

## Configuration

1. **Fichiers de configuration** :
   - `constants.py` : Paramètres de connexion et dossiers
   - `config/spam_keywords.txt` : Mots-clés de spam
   - `config/blacklist.txt` : Liste noire
   - `config/whitelist_from.txt` : Liste blanche des expéditeurs
   - `config/whitelist_to_cc.txt` : Liste blanche des destinataires

2. **Prérequis** :
   - Python 3.x
   - Modules Python standard (imaplib, email, argparse)

## Utilisation

### Installation

1. Clonez ce dépôt :
   ```bash
   git clone https://github.com/votre-utilisateur/email-filter.git
   cd email-filter
   ```

2. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

### Exécution

```bash
# Filtrer tous les emails (mode interactif)
./junk.sh

# Filtrer les 50 derniers emails (mode automatique)
./junk.sh -l 50 -y

# Filtrer un email spécifique par ID OVH
./junk.sh -e "votre-id-ovh"
```

### Options

| Option | Description |
|--------|-------------|
| `-l N` | Filtrer les N derniers emails |
| `-y` | Mode automatique (sans confirmation) |
| `-e ID` | Filtrer un email spécifique par ID OVH |

## Fonctionnement

1. Le script se connecte au serveur IMAP OVH
2. Il parcourt les emails selon le mode sélectionné
3. Pour chaque email, il vérifie :
   - Si l'expéditeur est dans la liste noire
   - Si l'expéditeur est dans la liste blanche
   - Si l'email contient des indicateurs de spam
   - Si les destinataires sont valides
4. Selon les résultats, l'email est déplacé vers :
   - Le dossier Junk (spam)
   - Le dossier Newsletters
   - Le dossier Archive
   - Ou laissé dans la boîte de réception

## Personnalisation

Vous pouvez adapter le filtrage en modifiant :
- `constants.py` pour les paramètres de connexion et dossiers
- Les fichiers de configuration dans le dossier `config`
- Les seuils de détection dans `spam_detection.py`

## Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir des issues ou des pull requests.

## Licence

[MIT](LICENSE)
```

Ce README explique clairement le but du projet, comment l'installer et l'utiliser, ainsi que les fonctionnalités principales. Vous pouvez bien sûr l'adapter selon vos besoins spécifiques.
