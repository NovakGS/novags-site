# Hamele downloads clipped to the parcel (2026-11-26)

One-off rebuild of the Hamele downloads so their maps match the clipped pages.
Inputs were the Drive originals; outputs live under hamele/*/files/ and the page links point there.

- clip_reports.py: swaps the clipped hamele/li-img maps into the Essentials, Due Diligence, and Stewardship PDFs.
- clipmask.py + clip_po_lg.py: masks the Property Overview PDF images (white) and the six Listing Graphics (footer color) outside the boundary; deer rings outside the line are kept, like the map page.
- clip_kmz.py: fixes the swapped LatLonBox in the Essentials, Due Diligence, and Stewardship KMZs, tiles each JPG overlay as an inner JPG plus four PNG edge strips (keeps file size down), makes thermal.png transparent outside, clips polygon and line layers to the boundary, keeps points and nearby-record layers, and drops Public land rings more than 5.5 km away (name-merged PAD-US records).
- render_kmz.py: quick raster check of a KMZ.

The PC tool still builds rectangles, so a rerun brings them back until it does this itself.
