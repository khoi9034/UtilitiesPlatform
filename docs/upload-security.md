# Upload Security

Local uploads are streamed to `C:\UtilitiesPlatform_Data\temp\uploads`, hashed incrementally with SHA-256, size-limited by `UTILITY_UPLOAD_MAX_BYTES`, then atomically moved into Raw storage only after validation passes.

Validation rejects unsupported extensions, executables, scripts, `.sde` files, encrypted ZIPs, nested archives, unsafe archive paths, symlinks, excessive member counts, excessive uncompressed size, high compression ratios, incomplete shapefile sidecars, and geodatabase ZIPs that do not contain exactly one `.gdb` directory.

The original package is preserved unchanged in the Raw submission `original` folder. Inspection files live separately and may be regenerated. APIs return safe filenames, hashes, statuses, and metadata, not absolute local paths or raw records.
