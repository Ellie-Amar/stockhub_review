# Contexte Métier de StockHub

## Aperçu

StockHub est un système de gestion des stocks pour les entreprises e-commerce qui vendent des produits sur plusieurs canaux de vente (leur propre site web, Amazon, Cdiscount, etc.). Ce document explique les concepts métier essentiels que vous devrez comprendre pour évaluer la base de code.

---

## Concepts Fondamentaux

### 1. Stock Physique vs. Stock Disponible

Le **stock physique** est le nombre réel d'unités présentes dans l'entrepôt. Mais tout le stock physique n'est pas disponible à la vente :

| Type de Stock | Définition | Exemple |
|---------------|------------|---------|
| Physique | Unités dans l'entrepôt | 100 unités en rayon |
| Réservé | Mis de côté pour des promotions ou des commandes en cours de traitement | 20 unités pour le Black Friday |
| En Transit | Expédié mais pas encore livré | 15 unités en route |
| Disponible | Ce qui peut réellement être vendu | 100 - 20 - 15 = 65 unités |

**Pourquoi c'est important :** Si vous ne suivez que le stock physique, vous pourriez afficher 100 unités disponibles alors que seulement 65 peuvent réellement être vendues.

### 2. Vente Multicanal

La plupart des entreprises e-commerce vendent le même produit sur plusieurs plateformes simultanément :

```
                    ┌──────────────┐
                    │   Entrepôt   │
                    │  Stock: 100  │
                    └──────┬───────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
   ┌──────────┐      ┌──────────┐      ┌──────────┐
   │  Amazon  │      │   Site   │      │ Cdiscount│
   │Affiché:80│      │Affiché:80│      │Affiché:80│
   └──────────┘      └──────────┘      └──────────┘
```

Les trois canaux puisent dans le même pool de 100 unités. Quand quelqu'un achète sur Amazon, nous devons mettre à jour **tous** les canaux pour éviter la survente.

### 3. Le Problème de la Survente

La **survente** se produit lorsque vous vendez plus d'unités que vous n'en possédez physiquement.

**Exemple de scénario :**
1. Vous avez 1 unité d'un gadget populaire
2. Le client A l'achète sur Amazon à 10:00:01
3. Le client B l'achète sur votre site web à 10:00:02
4. Les deux commandes sont confirmées avant que la synchronisation du stock ne soit terminée
5. **Résultat :** Vous devez 2 gadgets mais n'en avez qu'1

**Conséquences de la survente :**
- Remboursements et réclamations clients
- Les avis négatifs nuisent à la réputation de la marque
- Pénalités des marketplaces (Amazon peut suspendre les comptes vendeurs)
- Intervention manuelle nécessaire pour résoudre chaque cas

**Analogie :** La survente, c'est comme émettre des chèques sans provision. Votre « banque » (entrepôt) n'a pas les fonds (stock) pour couvrir tous les retraits (ventes).

### 4. Délais de Synchronisation des Marketplaces

Quand le stock change, nous devons mettre à jour chaque marketplace. Mais ces mises à jour ne sont **pas instantanées** :

| Canal | Délai de Sync Typique |
|-------|----------------------|
| Site propre | Millisecondes (accès direct BDD) |
| Amazon | 15 secondes à 15 minutes |
| Cdiscount | 30 secondes à 5 minutes |

**Analogie :** Pensez au stock des marketplaces comme au solde d'un distributeur automatique. Après avoir déposé de l'argent en agence, le distributeur peut encore afficher votre ancien solde pendant quelques minutes.

**Pourquoi c'est important :** Pendant les périodes de fort trafic (Black Friday, ventes flash), les délais de synchronisation peuvent causer des dizaines de surventes avant que l'inventaire ne rattrape son retard.

### 5. Mouvements de Stock

Chaque modification de l'inventaire est enregistrée comme un « mouvement » à des fins d'audit :

| Type de Mouvement | Direction | Exemple |
|-------------------|-----------|---------|
| VENTE | Diminution (-) | Le client a acheté 2 unités |
| RETOUR | Augmentation (+) | Le client a retourné 1 unité |
| RÉAPPROVISIONNEMENT | Augmentation (+) | Nouvelle livraison du fournisseur |
| AJUSTEMENT | L'un ou l'autre | Correction d'inventaire |

**Pourquoi suivre les mouvements :** Quand les chiffres du stock ne correspondent pas aux comptages physiques, vous devez tracer chaque changement pour trouver les écarts.

### 6. Flux des Retours

Les retours ne sont pas aussi simples que « l'article revient, on l'ajoute au stock » :

```
Le client expédie  →   L'entrepôt    →   Contrôle   →   Décision
   le retour           réceptionne       qualité

                                            │
                      ┌─────────────────────┼─────────────────────┐
                      ▼                     ▼                     ▼
                 Retour en stock       Reconditionné           Détruit
                 (Grade A)             (Grade B)               (Endommagé)
```

**Pourquoi c'est important :** Si vous ajoutez les articles retournés au stock immédiatement à réception, vous pourriez vendre un article défectueux avant que le contrôle qualité ne le détecte.

### 7. Réservations par Canal

Parfois, vous souhaitez réserver du stock pour des événements de vente spécifiques :

**Exemple :**
- Vous avez 200 unités
- Le Prime Day d'Amazon approche
- Vous réservez 50 unités exclusivement pour Amazon
- Votre site web et Cdiscount n'ont accès qu'aux 150 restantes

**Analogie :** C'est comme affecter une partie de votre budget à des projets spécifiques — cet argent n'est pas disponible pour les dépenses générales.

**Cycle de vie d'une réservation :**
1. Créer la réservation (50 unités pour Amazon, expire le 20 juillet)
2. Pendant le Prime Day, seul Amazon peut vendre ces 50 unités
3. Après expiration, les unités non réservées retournent au pool général

### 8. Alertes de Réapprovisionnement

Pour éviter les ruptures de stock, les systèmes déclenchent des alertes quand l'inventaire passe sous un seuil :

```
Niveau de Stock :  ████████████████░░░░░░░░░  64 unités
Seuil d'Alerte :   ────────────────────┼──    20 unités
                                        ↑
                                    L'alerte se déclenche
                                    quand stock ≤ 20
```

**L'alerte doit se déclencher quand :**
- Une vente fait passer le stock sous le seuil
- Un ajustement d'inventaire révèle un stock plus bas que prévu
- Le traitement d'un retour révèle des marchandises endommagées (diminution nette)

---

## Règles Métier Clés

1. **Cohérence du stock :** La somme de tous les mouvements doit être égale au stock actuel
2. **Pas de stock négatif :** Le système doit empêcher les ventes qui causeraient un inventaire négatif
3. **Synchronisation immédiate :** Tout changement de stock doit se propager à tous les canaux actifs
4. **Piste d'audit :** Chaque mouvement doit avoir une raison et un horodatage
5. **Respect des réservations :** Stock disponible = Physique - Réservé - En Transit

---

## Glossaire

| Terme | Définition |
|-------|------------|
| SKU | Stock Keeping Unit (Unité de Gestion des Stocks) - identifiant unique pour une variante de produit |
| Survente | Vendre plus d'unités que physiquement disponibles |
| Rupture de stock | Avoir zéro unité disponible (opportunité de vente manquée) |
| Sync | Mise à jour des listings marketplace avec les niveaux de stock actuels |
| Webhook | Callback HTTP que les marketplaces utilisent pour nous notifier d'événements |
| Idempotent | Une opération qui produit le même résultat si elle est exécutée plusieurs fois |
| Condition de concurrence | Bug où le résultat dépend du timing d'opérations simultanées |

---

## Questions à Considérer Lors de la Revue

En examinant la base de code, considérez :

1. Comment le système empêche-t-il la survente pendant les périodes de fort trafic ?
2. Que se passe-t-il si une synchronisation marketplace échoue ?
3. Comment les retours sont-ils gérés avant que le contrôle qualité ne soit terminé ?
4. Quelle piste d'audit existe quand les chiffres du stock ne correspondent pas ?
5. Comment le système gère-t-il la réception du même webhook deux fois ?
6. Que se passe-t-il quand deux ventes du même produit ont lieu simultanément ?