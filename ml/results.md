# Stage 10 AI results, version 2 (2026-11-01)

Version 2 predicts the change since the previous image and no longer uses field size (version 1 did not beat 'same as last time'; its results are kept in results_v1.md). These changes were made AFTER seeing version 1's test results, so version 2's test numbers are slightly optimistic.

Dataset: 10443 rows from 25 fields, years 2019-2025. Target: mean NDVI of the field on a clear satellite date.
MAE = mean absolute error in NDVI units (lower is better). Baselines use no AI.

## 1. Time split: train 2019-2023, settings chosen on 2024, test 2025
Chosen settings: {'learning_rate': 0.1, 'max_iter': 100, 'max_depth': 3} (validation MAE 0.0578)
Test rows compared: 1562 (0 rows with no seasonal history left out so all three methods are scored on the same rows)
```
model               MAE 0.0507
same as last time   MAE 0.0513
seasonal average    MAE 0.0839
```

## 2. Field split: 5 rounds, each holding out ~20% of the fields (all years)
Every field is predicted once, by a model that never saw that field. (The seasonal baseline uses the field's own other years, which the model never sees.)
Rows compared: 10443 (0 rows with no seasonal history left out)
```
model               MAE 0.0542
same as last time   MAE 0.0542
seasonal average    MAE 0.0764
```
By field type (field split, model vs. same as last time):
```
sports      4144 rows   model 0.0580   same as last time 0.0521
baseball    2138 rows   model 0.0433   same as last time 0.0499
park        4161 rows   model 0.0559   same as last time 0.0586
```

How far ahead the prediction is (field split): weather can only matter when there is time
for the grass to change, so errors are shown by days since the previous image.
```
 1-3  days   7630 rows   model 0.0525   same as last time 0.0518
 4-7  days   2151 rows   model 0.0587   same as last time 0.0590
 8-14 days    611 rows   model 0.0571   same as last time 0.0674
15-45 days     51 rows   model 0.0712   same as last time 0.0627
```

## Does the model beat the best baseline ('same as last time')?
Checked by re-drawing the fields at random 1000 times (bootstrap). Positive = model better.
- Time split, 2025, all rows (1562 rows): NO CLEAR DIFFERENCE: +0.0005 (+1%); the 95% range -0.0018 to +0.0027 includes 0, so it could be luck
- Field split, unseen fields, all rows (10443 rows): NO CLEAR DIFFERENCE: +0.0001 (+0%); the 95% range -0.0052 to +0.0039 includes 0, so it could be luck
- Field split, previous image 8+ days old (662 rows): YES, reliably: 0.0088 lower error (13% better); 95% range +0.0019 to +0.0145
- Time split, previous image 8+ days old (102 rows): NO CLEAR DIFFERENCE: +0.0020 (+4%); the 95% range -0.0067 to +0.0110 includes 0, so it could be luck

## 'Weather doesn't explain this' cutoff
Typical 2024 error (MAE) 0.0578; cutoff = 2 x that = 0.1156. In 2024, 6.4% of clear dates were more than this far below the model's expectation (the message would have shown).

## Which inputs matter most
How much worse the 2024 MAE gets when one input is shuffled (bigger = more important). Chart: feature_importance.png
```
previous NDVI                   0.1179  ##############################
days since previous image       0.0025  
avg high temp, 7 days           0.0014  
season (day of year)            0.0004  
rain minus ET0, 30 days         0.0002  
water demand (ET0), 7 days      0.0002  
avg high temp, 14 days          0.0002  
rain, last 30 days              0.0001  
rain, last 7 days               0.0001  
water demand (ET0), 30 days     0.0001  
water demand (ET0), 14 days     0.0000  
rain, last 14 days             -0.0000  
rain minus ET0, 14 days        -0.0002  
```
