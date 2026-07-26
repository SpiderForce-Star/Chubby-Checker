# Geometry-Based Length Formulas

When building length / width / eave height / roof slope are known, Chubby-Checker estimates expected accessory lengths.

## Gutter
```
expected_gutter_ft = sides × building_length
```
Default `sides = 2` (both eaves).

## Downspouts
```
expected_count ≈ ceil(eave_length / 40 ft), minimum 2 per side
```

## Eave Trim
```
expected_ft = sides × building_length
```

## Rake Trim
```
if slope known:
  rake_one = sqrt((width/2)² + rise²)
  expected_ft = 2 × rake_one
else:
  expected_ft = 2 × width   # conservative
```

## Corner Trim
```
expected_pieces = 4 (typical)
expected_ft = 4 × eave_height   (when height known)
```

## Base Trim
```
expected_ft = 2 × (length + width)   # perimeter
```

## Ridge Trim
```
expected_ft = building_length
```

## Thermal Blocks
- Target ratio vs sliding clips: **~1.0**
- Ratio < 0.85 → WARNING
- Zero blocks with clips + insulation → WARNING/CRITICAL
- Ratio > 1.20 → INFO (extras)

Pass a `BuildingGeometry` object into `DiscrepancyEngine` to activate length formula checks.
