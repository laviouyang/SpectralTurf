# Stage 10 AI results, VERSION 1 (2026-11-01) - kept for the record; superseded by results.md

Dataset: 10443 rows from 25 fields, years 2019-2025. Target: mean NDVI of the field on a clear satellite date.
MAE = mean absolute error in NDVI units (lower is better). Baselines use no AI.

## 1. Time split: train 2019-2023, settings chosen on 2024, test 2025
Chosen settings: {'learning_rate': 0.1, 'max_iter': 100, 'max_depth': 3} (validation MAE 0.0563)
Test rows compared: 1562 (0 rows with no seasonal history left out so all three methods are scored on the same rows)
```
model               MAE 0.0517
same as last time   MAE 0.0513
seasonal average    MAE 0.0839
```

## 2. Field split: 5 rounds, each holding out ~20% of the fields (all years)
Every field is predicted once, by a model that never saw that field. (The seasonal baseline uses the field's own other years, which the model never sees.)
Rows compared: 10443 (0 rows with no seasonal history left out)
```
model               MAE 0.0723
same as last time   MAE 0.0542
seasonal average    MAE 0.0764
```
By field type (field split, model vs. same as last time):
```
sports      4144 rows   model 0.0819   same as last time 0.0521
baseball    2138 rows   model 0.0457   same as last time 0.0499
park        4161 rows   model 0.0764   same as last time 0.0586
```

## Does the model beat the baselines?
- Time split (2025): NO: the best baseline (same as last time) is as good or better by 0.0004.
- Field split (unseen fields): NO: the best baseline (same as last time) is as good or better by 0.0181.

## 'Weather doesn't explain this' cutoff
Typical 2024 error (MAE) 0.0563; cutoff = 2 x that = 0.1126. In 2024, 5.9% of clear dates were more than this far below the model's expectation (the message would have shown).

## Which inputs matter most
How much worse the 2024 MAE gets when one input is shuffled (bigger = more important). Chart: feature_importance.png
```
previous NDVI                   0.1024  ##############################
field size                      0.0078  ##
season (day of year)            0.0025  
days since previous image       0.0022  
avg high temp, 7 days           0.0008  
rain, last 30 days              0.0005  
rain, last 7 days               0.0003  
avg high temp, 14 days          0.0002  
water demand (ET0), 7 days      0.0002  
rain, last 14 days              0.0001  
rain minus ET0, 14 days         0.0000  
rain minus ET0, 30 days         0.0000  
water demand (ET0), 30 days    -0.0000  
water demand (ET0), 14 days    -0.0001  
```
