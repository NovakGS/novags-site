# Hamele downloads clipped to the parcel (2026-11-26)

One-off rebuild of the Hamele downloads so their maps match the clipped pages.
Inputs were the Drive originals; outputs live under hamele/*/files/ and the page links point there.

- clip_reports.py: swaps the clipped hamele/li-img maps into the Essentials, Due Diligence, and Stewardship PDFs.
- clipmask.py + clip_po_lg.py: masks the Property Overview PDF images (white) and the six Listing Graphics (footer color) outside the boundary; deer rings outside the line are kept, like the map page.
- clip_kmz.py: fixes the swapped LatLonBox in the Essentials, Due Diligence, and Stewardship KMZs, tiles each JPG overlay as an inner JPG plus four PNG edge strips (keeps file size down), makes thermal.png transparent outside, clips polygon and line layers to the boundary, keeps points and nearby-record layers, and drops Public land rings more than 5.5 km away (name-merged PAD-US records).
- render_kmz.py: quick raster check of a KMZ.

The PC tool still builds rectangles, so a rerun brings them back until it does this itself.

## Squared to a rectangle (2026-11-26, later)

The parcel outline was a slightly slanted quadrilateral, so the clipped maps looked crooked. Every map now uses a
straight rectangle of the same 33.3 ac: frame units x 58.8 to 3527.0, y 73.4 to 2888.0 (hamele/img/vec.json boundary,
the map page clip-path), and in Google Earth the north-up box W -89.62739055, E -89.62238155, N 43.1120397, S 43.1090618.

- square_li.py: redraws the seven hamele/li-img report maps on the rectangle (inputs were the earlier clipped maps).
- square_po_lg.py + cmask.py + render_frame.py: the Property Overview PDF maps and the six Listing Graphics. The old
  slanted line was baked into these, so the strip under it is rebuilt from the clean map layers (aerial, thermal,
  relief, elevation tiles) plus a smooth correction; on Elevation & Contours the contours are redrawn from vec.json
  and contour labels cut by the frame are taken out. Deer rings stay whole, like the markers on the map page.
- clip_kmz.py: now clips to the rectangle and replaces the Boundary placemark with it (the quadrilateral version is
  kept in git history).
- clip_reports.py: unchanged; rerun to swap the squared li-img maps into the three report PDFs.

Not redone here: the hunting-app files ZIP and the GeoJSON and GPX copies in the Drive folders still carry the
quadrilateral outline.
