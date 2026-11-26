# Hamele round 3

Gregg's round-3 notes on the package pages.

- `side_labels.py`: draws the approximate side lengths on the Essentials overview map (`map_overview.jpg`), from the clean frame `overview_base.jpg`.
- `contour_map.py`: builds `map_contours.jpg` (2-ft contours, 10-ft index lines, labels every 20 ft) from the 2024 bare-earth LiDAR.
- `pond_legend.py`: relabels the pond map legend in plain words (Land draining to the site, Pond with an 8 ft dam, Dam site).
- `../essentials-move/li_reports.py` rebuilds the Essentials report with the new Contours page.

Page edits: Stewardship reordered (herd, trails and food plots, canopy, erosion); Due Diligence reordered (build areas, ground and water, zoning, ponds, soils, then parcels, surroundings, historical maps), soil-rating definitions added, pond table set one row per pond with both dam heights side by side.

## PDFs (2026-11-26)

- reports_dd_st.py: rebuilds the Buyer Due Diligence Report (10 pages) and the Stewardship Baseline Report (3 pages) in the
  house style from essentials-move/li_reports.py, using the same map images as the pages (hamele/li-img).
  Due Diligence follows the page order: build sites (with the NRCS rating definitions under the table), ground and water,
  zoning, ponds (one row per pond, 8 ft and 12 ft dams side by side, with the how-to-read note), soils, parcels, what is
  around it, historical maps, sources. Stewardship: baseline, deer herd baseline, cover and canopy, erosion watch, repeat
  photo points, land-use history.
  Run: python3 reports_dd_st.py <out_dir>, then copy the two PDFs into hamele/due-diligence/files and hamele/stewardship/files.
