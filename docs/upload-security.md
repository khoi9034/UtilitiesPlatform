# Upload Security

Local uploads are streamed to `C:\UtilitiesPlatform_Data\temp\uploads`, hashed incrementally with SHA-256, size-limited by `UTILITY_UPLOAD_MAX_BYTES`, then atomically moved into Raw storage only after validation passes. Direct FileGDB folder uploads are also capped by `UTILITY_UPLOAD_MAX_FILES`, defaulting to `50000`.

Direct FileGDB paths use one policy in the browser and backend: one relative top-level `.gdb` root; no empty, dot, parent, absolute, duplicate, or multi-root paths; and path components limited to letters, digits, spaces, `.`, `_`, and `-`. The package must contain a top-level `gdb` or `.gdbtable` system file. Recognized `.lock`, `.sr.lock`, and `.tmp` files are omitted before transfer and recorded in the private submission manifest; unknown files are never silently ignored.

Upload validation errors return a safe code, message, retry guidance, and request ID. Responses never include absolute paths, multipart values, source records, credentials, or tracebacks.

Validation rejects unsupported extensions, executables, scripts, `.sde` files, encrypted ZIPs, nested archives, unsafe archive paths, symlinks, excessive member counts, excessive uncompressed size, high compression ratios, incomplete shapefile sidecars, and geodatabase ZIPs that do not contain exactly one `.gdb` directory.

For direct `.gdb` folders, the browser performs preliminary checks and the backend repeats authoritative validation. The backend accepts a separate `relative_paths` list, rejects mismatched file/path counts, path traversal, absolute paths, drive letters, UNC paths, empty components, duplicate normalized paths, multiple top-level roots, non-`.gdb` roots, unsupported internal executable/script files, excessive file counts, and aggregate bytes above the limit. Destination paths are never supplied by the frontend.

Folder-package duplicate detection uses SHA-256 over a canonical UTF-8 manifest of sorted records: normalized relative path, file size, and per-file SHA-256. File timestamps are ignored.

The original package is preserved unchanged in the Raw submission `original` folder. Inspection files live separately and may be regenerated. APIs return safe filenames, hashes, statuses, and metadata, not absolute local paths or raw records.
