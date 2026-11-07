# Stage 10 AI results, VERSION 3 (2026-11-07)

What changed from version 2 (student decision 2026-11-07):
1. The model predicts NDVI 7-20 days after a clear image (every pair of clear images that far apart), not the next back-to-back image. This is what the app asks (next week, 14-day What-if).
2. New inputs: average of recent images, recent trend, image quality, weather compared with the Denver-area normal (2019-2024), and the field's own usual NDVI (earlier years).
3. Three likely artificial-turf fields removed: sports #1: likely artificial turf (NDVI ~0.31 all season, green in photos); sports #2: likely artificial turf (NDVI ~0.45 flat, red-track complex); sports #3: likely artificial turf (NDVI ~0.42 flat, green in Nov photo).

Honesty notes: which inputs, starting point and settings to use was chosen on 2024 only; 2025 was tested once, by this file. But the version 3 IDEAS came after seeing the version 1 and 2 test results, so these test numbers are still slightly optimistic. Version 3 answers a different (harder) question than versions 1-2 (7-20 days ahead instead of the next image, usually 1-3 days), so compare each version with its own baselines, not the raw MAEs across versions.

Dataset: 38342 rows (start -> target pairs) from 22 fields, target years 2019-2025. Target: mean NDVI of the field on the target date.
MAE = mean absolute error in NDVI units (lower is better). Baselines use no AI.

## 0. Chosen on 2024 only (trained 2019-2023)
```
A (version 2 inputs)                                       start = start image               MAE 0.0691
A (version 2 inputs)                                       start = average of recent images  MAE 0.0667
B (+ smoothing, trend, image quality, weather vs normal)   start = start image               MAE 0.0611  <- chosen
B (+ smoothing, trend, image quality, weather vs normal)   start = average of recent images  MAE 0.0613
C (B + field's own usual NDVI)                             start = start image               MAE 0.0631
C (B + field's own usual NDVI)                             start = average of recent images  MAE 0.0623
```
Chosen: input set B (+ smoothing, trend, image quality, weather vs normal), start = start image, settings {'learning_rate': 0.05, 'max_iter': 200, 'max_depth': 3}.

## 1. Time split: train 2019-2023, chosen on 2024, test 2025 (run once)
Test rows compared: 5831 (0 rows with no seasonal history left out)
```
model               MAE 0.0577
same as last time   MAE 0.0686
recent average      MAE 0.0686
seasonal average    MAE 0.0859
version 2 design    MAE 0.0611   (same rows; trained on back-to-back images, same 22 fields)
```

## 2. Field split: 5 rounds, each holding out ~20% of the fields (all years)
Rows compared: 38342 (0 rows with no seasonal history left out)
```
model               MAE 0.0600
same as last time   MAE 0.0694
recent average      MAE 0.0664
seasonal average    MAE 0.0764
```
By field type (field split):
```
sports     12058 rows   model 0.0585   same as last time 0.0690   recent average 0.0656
baseball    9063 rows   model 0.0441   same as last time 0.0583   recent average 0.0551
park       17221 rows   model 0.0693   same as last time 0.0755   recent average 0.0729
```
By days ahead (field split):
```
 7-10 days  13006 rows   model 0.0551   same as last time 0.0619   recent average 0.0594
11-14 days   6566 rows   model 0.0605   same as last time 0.0715   recent average 0.0679
15-20 days  18770 rows   model 0.0631   same as last time 0.0738   recent average 0.0707
```

## Does version 3 beat the baselines? (1,000 re-draws of the fields)
Positive = model better. 'Reliably' = the middle 95% of the re-draws is entirely above 0.
- 2025 vs same as last time (5831 rows): YES, reliably: 0.0109 lower error (16% better); 95% range +0.0075 to +0.0143
- 2025 vs recent average (5831 rows): YES, reliably: 0.0109 lower error (16% better); 95% range +0.0075 to +0.0142
- 2025 vs seasonal average (5831 rows): YES, reliably: 0.0282 lower error (33% better); 95% range +0.0096 to +0.0540
- Unseen fields vs same as last time (38342 rows): YES, reliably: 0.0094 lower error (14% better); 95% range +0.0007 to +0.0150
- Unseen fields vs recent average (38342 rows): NO CLEAR DIFFERENCE: +0.0064 (+10%); the 95% range -0.0017 to +0.0115 includes 0, so it could be luck
- Unseen fields vs seasonal average (38342 rows): YES, reliably: 0.0164 lower error (21% better); 95% range +0.0079 to +0.0280
- 2025 vs version 2 design on the same question: YES, reliably: 0.0035 lower error (6% better); 95% range +0.0007 to +0.0060

## Versions 1, 2 and 3 side by side (each with its own baselines)
v1/v2: next back-to-back image, 25 fields (results_v1.md, results_v2.md). v3: 7-20 days ahead, 22 fields. 'vs last time' = how much lower the model's error is than 'same as last time' (positive = better).
```
           2025 model  last time  seasonal  vs last    unseen model  last time  seasonal  vs last
v1             0.0517     0.0513    0.0839      -1%          0.0723     0.0542    0.0764     -33%
v2             0.0507     0.0513    0.0839      +1%          0.0542     0.0542    0.0764      +0%
v3             0.0577     0.0686    0.0859     +16%          0.0600     0.0694    0.0764     +14%
```

## 'Weather doesn't explain this' cutoff
Typical 2024 error (MAE) 0.0611; cutoff = 2 x that = 0.1222. In 2024, 7.9% of pairs were more than this far below the model's expectation.

## Which inputs matter most
How much worse the 2024 MAE gets when one input is shuffled. Chart: feature_importance_v3.png
```
start image NDVI                    0.0846  ##############################
recent trend (per day)              0.0133  ####
season (day of year)                0.0036  #
start image pixel spread            0.0015  
rain, last 14 days                  0.0011  
rain minus ET0, 30 days             0.0007  
rain, last 30 days                  0.0005  
days ahead                          0.0004  
avg high temp, 7 days               0.0004  
rain 14 days vs normal              0.0004  
rain minus ET0, 14 days             0.0004  
avg high temp, 14 days              0.0003  
rain, last 7 days                   0.0003  
water demand (ET0), 30 days         0.0003  
start image clear fraction          0.0002  
water demand (ET0), 7 days          0.0001  
high temp 14 days vs normal         0.0000  
rain minus ET0 14 days vs normal   -0.0000  
average of recent images           -0.0000  
high temp 7 days vs normal         -0.0000  
water demand (ET0), 14 days        -0.0001  
```
