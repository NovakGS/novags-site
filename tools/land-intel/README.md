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
