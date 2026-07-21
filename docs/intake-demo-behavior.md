# Intake Demo Behavior

Portfolio demo mode mirrors the intake workflow without uploading, reading, or transmitting files.

On `/data-sources/upload`, demo users can load **Load Synthetic Mixed FileGDB**, a synthetic sample that is not a committed real geodatabase. They can also select a local package file or a `.gdb` folder for metadata-only simulation. Folder simulation uses safe browser metadata such as root name, file count, total size, and relative filenames; it does not upload contents, read bytes, compute a real checksum, or imply ArcPy inspected the selected folder.

Demo intake never calls FastAPI and never persists beyond the browser session. All inventory, classification, and Raw-stage results are synthetic or sanitized.
