# Intake Demo Behavior

Portfolio demo mode mirrors the intake workflow without uploading, reading, or transmitting files.

On `/data-sources/upload`, demo users can load `Sample_Wastewater_Extension.zip`, a synthetic sample name that is not a committed real ZIP. They can also select a local file for metadata-only simulation. The demo uses browser-provided filename, size, and MIME metadata only, stores temporary results in `sessionStorage`, and resets with **Reset Demo Intake**.

Demo intake never calls FastAPI and never persists beyond the browser session. All inventory, classification, and Raw-stage results are synthetic or sanitized.
