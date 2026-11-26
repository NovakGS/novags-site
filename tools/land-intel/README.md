# Land Intelligence client pages

Turns one job's Land Intelligence build into branded client pages with working downloads.

1. On the PC, run **Make Land Intel** (desktop shortcut). It builds
   `04_Deliverables\Land_Intel\` (four package folders + `land_intel.json`) and copies the
   package folders to `G:\My Drive\Land Intelligence\<job>\`.
2. Collect the Drive file IDs into `clients/<client>/drive_links.json`
   (`{"folder": id, "packages": {"1 Essentials": {"folder": id, "files": {"<file name>": "<id>"}}}}`).
   The folders are shared "anyone with the link" once, at the `Land Intelligence` level.
3. Copy `land_intel.json` and the map images (`_work\*.png`) into `clients/<client>/`.
4. `python tools/land-intel/build_pages.py tools/land-intel/clients/<client>.json`

The client file names the branded page to borrow the header, footer, contact block, and CSS from,
so new pages always match the client's look. Package 2 can point at an existing page; its download
links are switched to Drive and the package switcher is added above its downloads.

## EXIT Professional Real Estate version

Same packages in EXIT's look, with EXIT's names (2 Country Property, 4 New Owner Stewardship), the
listing agent's card, and a presentation page at `/exit/`. The sample job is 26-239 at
`/exit/33-acre-cross-plains/`.

1. On the PC, after Make Land Intel, run **Make EXIT Package** (desktop shortcut; the script is
   `pc/MakeExitPackage.ps1` and installs itself on first run). It copies the package files to
   `G:\My Drive\EXIT Land Intelligence\<job> <listing name>\` with the EXIT names (renaming the app
   file folders and the map name inside the KMZ), and puts `land_intel.json`, the map images, the
   original PDFs, and `exit_job.json` in `G:\My Drive\EXIT Build Files\<job>\`, which is never shared.
   `EXIT Land Intelligence` is shared "anyone with the link" once, the same way as `Land Intelligence`.
2. Build the standard pages for the job into a staging folder with `build_pages.py` (a client file
   like `hamele.json` with `"site_root"` set). Package 2's interactive map page is built by hand for
   each job, as it was for Hamele.
3. Copy `clients/exit.json` to `clients/exit-<job>.json` and change `job`, `source`, `dest`,
   `path_map`, `property` (name, place, county, acres, flight pill, facts, crumbs), `agent`,
   `pdf_text`, `kmz_text`, and the overview title in `pdfs`. `{job}` in any value stands for the job
   number. Put the EXIT folder's Drive file IDs in `drive_links`.
4. `python3 tools/land-intel/reskin.py tools/land-intel/clients/exit-<job>.json` copies the files,
   renames them, rebrands the PDFs, and writes the four pages. Add the four rebranded PDFs to the
   EXIT Drive folder and their IDs to `drive_links`, then run it again with `--pages-only`.
5. `python3 tools/land-intel/build_pitch.py tools/land-intel/clients/exit-<job>.json` rebuilds the
   presentation page, only when it should change.
6. Push to a preview branch. Going live is a merge, and only on Gregg's OK.
