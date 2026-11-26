# Soils and drainage moved from Essentials to Due Diligence (2026-11-26)

Essentials now covers the land, how it lies, and where the water goes; soils and drainage live in Buyer Due Diligence.
FEMA flood stays in Essentials. All figures are measured on the squared flight boundary (33.33 ac).

- unhydric.py: takes the hydric-soil overlay off hamele/li-img/map_water.jpg (relief rebuilt from the ponds and zoning
  maps, which share its base) and shortens the legend to three rows.
- relief_base.py + slope_map.py: hamele/li-img/map_slope.jpg, five slope classes from the 2024 bare-earth LiDAR
  (2x2 block mean, gaussian sigma 1, Horn slope) over the shaded relief. slope_classes.py prints the class acres,
  elevation range, and side lengths.
- li_reports.py: rebuilds the Essentials Report (glance table with boundary dimensions, Lay of the Land with the slope
  map and class table, Where the Water Goes with the water summary) and two Soils and Drainage pages for Due Diligence.
- dd_splice.py: inserts those two pages after page 2 of the Due Diligence Report, renumbers the footers, and adds
  "soils" to the page 1 subtitle.
- move_soils_kmz.py: moves the Soils (NRCS) folder from the Essentials KMZ to the Due Diligence KMZ and adds the side
  lengths to the Essentials boundary (description plus four side labels).
- GIS ZIPs are now hosted on the site: Essentials without soils and hydric indicators (boundary squared), Due Diligence
  with them added.

Boundary dimensions are rounded to the nearest 5 ft: about 1,340 ft north and south, 1,085 ft east and west,
4,850 ft around. Approximate, measured on the map, not a survey.

Not redone: the Google Drive package folders still hold the older copies, and the PC tool still builds the old layout.
