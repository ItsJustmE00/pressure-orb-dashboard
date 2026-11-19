# ORB Pressure - test statistique du coupe-circuit horaire

- Reechantillonnage par session NY, 5000 tirages, graine 20261119.
- Comparaison appariee : memes dates pour la baseline et la variante.
- `p<=0` = part des tirages ou la variante ne fait pas mieux que la baseline.

## Statistiques par periode

| variante | periode | trades | R moyen | R total | DD max % | pire journee R |
|:---------|:--------|-------:|--------:|--------:|---------:|---------------:|
| baseline | all | 4993 | 0.0275 | 137.3 | 19.3 | -7.27 |
| baseline | is | 2562 | 0.0288 | 73.8 | 18.1 | -5.71 |
| baseline | oos | 1901 | 0.0204 | 38.8 | 19.3 | -7.27 |
| baseline | recent | 530 | 0.0467 | 24.8 | 14.8 | -3.91 |
| cut14 | all | 3735 | 0.0560 | 209.0 | 16.9 | -4.86 |
| cut14 | is | 1863 | 0.0607 | 113.0 | 13.7 | -4.86 |
| cut14 | oos | 1462 | 0.0421 | 61.6 | 16.9 | -4.22 |
| cut14 | recent | 410 | 0.0839 | 34.4 | 11.4 | -4.07 |
| cut15 | all | 4052 | 0.0509 | 206.2 | 15.0 | -5.28 |
| cut15 | is | 2032 | 0.0583 | 118.4 | 14.2 | -4.89 |
| cut15 | oos | 1598 | 0.0374 | 59.8 | 15.0 | -5.28 |
| cut15 | recent | 422 | 0.0663 | 28.0 | 12.4 | -4.07 |
| cut16 | all | 4337 | 0.0405 | 175.6 | 15.2 | -6.27 |
| cut16 | is | 2183 | 0.0477 | 104.1 | 15.0 | -4.89 |
| cut16 | oos | 1709 | 0.0264 | 45.1 | 15.2 | -6.27 |
| cut16 | recent | 445 | 0.0593 | 26.4 | 12.4 | -4.07 |
| max2_cut15 | all | 3689 | 0.0483 | 178.1 | 18.7 | -2.65 |
| max2_cut15 | is | 1850 | 0.0607 | 112.2 | 14.2 | -2.65 |
| max2_cut15 | oos | 1435 | 0.0233 | 33.4 | 18.7 | -2.37 |
| max2_cut15 | recent | 404 | 0.0804 | 32.5 | 11.0 | -2.08 |

## Bootstrap apparie contre la baseline

| variante | delta R total | IC 95 % | p<=0 | delta R moyen | IC 95 % | p<=0 |
|:---------|--------------:|:--------|-----:|--------------:|:--------|-----:|
| cut14 | +71.1 | [+19.7 ; +125.8] | 0.004 | +0.0284 | [+0.0145 ; +0.0423] | 0.000 |
| cut15 | +68.6 | [+27.6 ; +109.9] | 0.000 | +0.0234 | [+0.0131 ; +0.0336] | 0.000 |
| cut16 | +38.1 | [+4.2 ; +72.6] | 0.013 | +0.0130 | [+0.0050 ; +0.0209] | 0.000 |
| max2_cut15 | +39.8 | [-17.3 ; +96.8] | 0.081 | +0.0206 | [+0.0058 ; +0.0355] | 0.004 |

Lecture : un intervalle de confiance entièrement positif indique que la variante bat la baseline sur la majorité des tirages. Le test ne prouve pas un gain futur ; il vérifie que le gain historique n'est pas un simple effet de quelques journées.
