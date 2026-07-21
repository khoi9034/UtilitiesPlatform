"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { getDataProvider, isDemoMode } from "../../lib/data-provider/provider";
import type { IntakeCapabilities, IntakeSubmission } from "../../lib/data-provider/types";
import { compactNumber, label, safeText } from "../../lib/formatters";
import { resetDemoIntake } from "../../lib/data-provider/demo-review-store";
import { EmptyState, Panel, StageBadge, StatusBadge, workspaceStyles as ws } from "../ui/Primitives";
import styles from "./data-sources.module.css";

const utilitySystems = ["water", "wastewater", "stormwater", "telecom", "electric", "gas", "shared_reference", "mixed", "unknown", "review_required"];
const sensitivities = ["public", "internal", "restricted", "highly_restricted"];

export function UploadDataWorkspace() {
  const provider = getDataProvider();
  const [capabilities, setCapabilities] = useState<IntakeCapabilities | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [status, setStatus] = useState("queued");
  const [message, setMessage] = useState("");
  const [receipts, setReceipts] = useState<IntakeSubmission[]>([]);
  const [form, setForm] = useState({
    submission_name: "",
    utility_system: "wastewater",
    source_type: "approved_source_package",
    source_owner: "",
    source_description: "",
    sensitivity_level: "restricted",
    project_id: "",
    submitted_by: "",
    authorization_confirmed: false,
    run_inventory_after_upload: false,
  });

  useEffect(() => {
    provider.getIntakeCapabilities().then(setCapabilities).catch(() => setMessage("Intake capabilities are unavailable. Start FastAPI for local uploads."));
  }, [provider]);

  const preliminary = useMemo(() => files.map((file) => ({ file, format: detectFormat(file.name), valid: Boolean(detectFormat(file.name)) })), [files]);
  const canSubmit = (files.length > 0 || isDemoMode) && form.submission_name && form.source_owner && form.source_description && form.authorization_confirmed;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit) {
      setMessage("Complete source metadata and authorization before upload.");
      return;
    }
    setReceipts([]);
    setStatus("uploading");
    try {
      const targets = isDemoMode && files.length === 0 ? [null] : files;
      const nextReceipts: IntakeSubmission[] = [];
      for (const file of targets) {
        const body = formData(file, false);
        const response = await provider.createIntakeSubmission(body);
        nextReceipts.push(...response.submissions);
      }
      setStatus("registered_raw");
      setReceipts(nextReceipts);
      setMessage(isDemoMode ? "Demo mode does not upload or inspect your file. The workflow is simulated using synthetic results." : "Package registered in local Raw storage.");
    } catch (error) {
      setStatus("failed");
      setMessage(error instanceof Error ? error.message : "Upload failed safely.");
    }
  }

  async function loadSyntheticSample() {
    setStatus("uploading");
    const response = await provider.createIntakeSubmission(formData(null, true));
    setReceipts(response.submissions);
    setStatus("inventory_complete");
    setMessage("Synthetic sample loaded into session-only demo intake.");
  }

  function formData(file: File | null, demoSample: boolean) {
    const data = new FormData();
    if (file) data.append("files", file, file.name);
    data.append("demo_sample", String(demoSample));
    for (const [key, value] of Object.entries(form)) data.append(key, String(value));
    data.set("submission_name", form.submission_name || (demoSample ? "Synthetic Mixed Utility Source" : "Metadata-Only Demo Source"));
    data.set("source_owner", form.source_owner || "Synthetic Data Owner");
    data.set("source_description", form.source_description || "Session-only portfolio demo intake simulation.");
    data.set("authorization_confirmed", String(form.authorization_confirmed || demoSample));
    return data;
  }

  function onFileSelect(selected: FileList | null) {
    setFiles(Array.from(selected ?? []));
    setStatus("queued");
    setReceipts([]);
  }

  return (
    <div className={ws.workspace}>
      <header className={ws.pageHeader}>
        <span className={ws.eyebrow}>{isDemoMode ? "PORTFOLIO DEMO INTAKE" : "LOCAL INTAKE"}</span>
        <h1>Upload Utility Data</h1>
        <p>Register approved source packages into immutable local Raw storage before inventory, QA, and staging review.</p>
      </header>

      <Panel title={isDemoMode ? "Demo Mode" : "Local Storage Warning"} description={isDemoMode ? "Demo mode does not upload or inspect your file. The workflow is simulated using synthetic results." : "Uploads remain on this workstation and are not sent to the public portfolio demo."}>
        <div className={ws.buttonRow}>
          {isDemoMode ? <button className={`${ws.button} ${ws.buttonPrimary}`} onClick={loadSyntheticSample}>Load Synthetic Sample</button> : null}
          {isDemoMode ? <button className={ws.button} onClick={() => { resetDemoIntake(); setReceipts([]); setMessage("Demo intake reset."); }}>Reset Demo Intake</button> : null}
          <Link className={ws.button} href="/data-sources?stage=raw">View Raw Stage</Link>
        </div>
      </Panel>

      <form className={styles.uploadGrid} onSubmit={submit}>
        <div className={ws.workspace}>
          <Panel title="Step 1 - Select Package" description="Each selected file is registered as a separate logical source package. Shapefiles and file geodatabases must be uploaded as ZIP packages.">
            <label
              className={styles.dropZone}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                onFileSelect(event.dataTransfer.files);
              }}
            >
              <calcite-icon icon="upload" scale="l" />
              <strong>Drop packages here or choose files</strong>
              <span className={styles.muted}>Supported: ZIP shapefile or geodatabase packages, DWG, DXF, GPKG, CSV, XLSX, PDF.</span>
              <input type="file" multiple onChange={(event) => onFileSelect(event.target.files)} />
            </label>
            <div className={styles.fileList}>
              {preliminary.length ? preliminary.map(({ file, format, valid }) => (
                <div className={styles.fileItem} key={`${file.name}-${file.size}`}>
                  <strong>{file.name}</strong>
                  <span className={styles.muted}>{compactNumber(file.size)} bytes - {format ? label(format) : "Unsupported"} - {valid ? "Preliminary format accepted" : "Rejected by browser precheck"}</span>
                  <button className={ws.button} type="button" onClick={() => setFiles((current) => current.filter((item) => item !== file))}>Remove</button>
                </div>
              )) : <EmptyState title={isDemoMode ? "No file selected" : "No package selected"} message={isDemoMode ? "Load the synthetic sample or select a local file for metadata-only simulation." : "Select an approved local source package before upload."} />}
            </div>
          </Panel>

          <Panel title="Step 2 - Describe Source" description="Detailed utility infrastructure defaults to restricted. Public export approval is not granted by intake.">
            <div className={styles.formGrid}>
              <label>Submission name<input className={ws.input} value={form.submission_name} onChange={(event) => setForm({ ...form, submission_name: event.target.value })} /></label>
              <label>Utility system<select className={ws.select} value={form.utility_system} onChange={(event) => setForm({ ...form, utility_system: event.target.value })}>{utilitySystems.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
              <label>Source type<input className={ws.input} value={form.source_type} onChange={(event) => setForm({ ...form, source_type: event.target.value })} /></label>
              <label>Source owner<input className={ws.input} value={form.source_owner} onChange={(event) => setForm({ ...form, source_owner: event.target.value })} /></label>
              <label>Sensitivity<select className={ws.select} value={form.sensitivity_level} onChange={(event) => setForm({ ...form, sensitivity_level: event.target.value })}>{sensitivities.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></label>
              <label>Project ID<input className={ws.input} value={form.project_id} onChange={(event) => setForm({ ...form, project_id: event.target.value })} /></label>
              <label>Submitted by<input className={ws.input} value={form.submitted_by} onChange={(event) => setForm({ ...form, submitted_by: event.target.value })} /></label>
              <label className={styles.fullWidth}>Description<textarea className={ws.input} value={form.source_description} onChange={(event) => setForm({ ...form, source_description: event.target.value })} /></label>
              <label className={`${styles.checkRow} ${styles.fullWidth}`}><input type="checkbox" checked={form.authorization_confirmed} onChange={(event) => setForm({ ...form, authorization_confirmed: event.target.checked })} /> I am authorized to store and analyze this source in the local Utilities Platform environment.</label>
              <label className={`${styles.checkRow} ${styles.fullWidth}`}><input type="checkbox" checked={form.run_inventory_after_upload} onChange={(event) => setForm({ ...form, run_inventory_after_upload: event.target.checked })} /> Run inventory after upload</label>
            </div>
          </Panel>
        </div>

        <aside className={ws.workspace}>
          <Panel title="Step 3 - Validate" description="Browser checks are preliminary; FastAPI validation is authoritative in local mode.">
            <dl className={styles.metadataList}>
              <div><dt>Metadata</dt><dd>{canSubmit ? "Complete enough to submit" : "Missing required fields or authorization"}</dd></div>
              <div><dt>Size limit</dt><dd>{compactNumber(capabilities?.maximum_upload_bytes)} bytes</dd></div>
              <div><dt>Package count</dt><dd>{compactNumber(files.length)}</dd></div>
              <div><dt>Authorization</dt><dd>{form.authorization_confirmed ? "Confirmed" : "Required"}</dd></div>
            </dl>
          </Panel>

          <Panel title="Step 4 - Upload" description="No automatic staging, repair, publication, standardization, curation, or export occurs.">
            <div className={styles.progressTrack}><div className={styles.progressFill} style={{ "--progress-width": progress(status) } as React.CSSProperties} /></div>
            <p className={styles.muted}>{label(status)}</p>
            <button className={`${ws.button} ${ws.buttonPrimary}`} type="submit" disabled={!canSubmit}>{isDemoMode ? "Simulate Intake" : "Upload to Local Raw"}</button>
            {message ? <p className={styles.muted}>{message}</p> : null}
          </Panel>

          <Panel title="Step 5 - Receipt" description="Safe receipt only; absolute paths are not included.">
            {receipts.length ? (
              <div className={styles.receiptList}>
                {receipts.map((receipt) => (
                  <div className={styles.receiptItem} key={receipt.submission_id}>
                    <strong>{receipt.submission_id}</strong>
                    <span>{receipt.original_filename}</span>
                    <span className={styles.muted}>SHA-256 {safeText(receipt.sha256_prefix)} - {compactNumber(receipt.file_size_bytes as number)} bytes</span>
                    <span><StageBadge value={receipt.current_status} /> <StatusBadge value={receipt.inventory_status} /></span>
                    <span className={styles.muted}>{receipt.next_required_action}</span>
                    <div className={ws.buttonRow}>
                      <Link className={ws.button} href="/data-sources?stage=raw">View in Raw Stage</Link>
                      <Link className={ws.button} href={`/data-sources/submission?id=${encodeURIComponent(receipt.submission_id)}`}>View Submission</Link>
                      <button className={ws.button} type="button" onClick={() => provider.startIntakeInventory(receipt.submission_id).then(() => setMessage("Inventory action completed."))}>Run Inventory</button>
                      <button className={ws.button} type="button" onClick={() => downloadReceipt(receipt)}>Download Safe Receipt</button>
                    </div>
                  </div>
                ))}
              </div>
            ) : <EmptyState title="No receipt yet" message="A successful local registration or demo simulation creates a safe receipt here." />}
          </Panel>
        </aside>
      </form>
    </div>
  );
}

function detectFormat(name: string) {
  const extension = name.toLowerCase().split(".").pop();
  if (extension === "zip") return "shapefile or file_geodatabase";
  if (extension === "gpkg") return "geopackage";
  if (extension === "dwg" || extension === "dxf") return "cad";
  if (extension === "csv" || extension === "xlsx") return "spreadsheet";
  if (extension === "pdf") return "pdf";
  return "";
}

function progress(status: string) {
  if (status === "queued") return "8%";
  if (status === "uploading") return "45%";
  if (status === "registered_raw" || status === "inventory_complete") return "100%";
  if (status === "failed") return "100%";
  return "20%";
}

function downloadReceipt(receipt: IntakeSubmission) {
  const safe = {
    submission_id: receipt.submission_id,
    submission_name: receipt.submission_name,
    original_filename: receipt.original_filename,
    source_format: receipt.source_format,
    utility_system: receipt.utility_system,
    sensitivity_level: receipt.sensitivity_level,
    current_status: receipt.current_status,
    inventory_status: receipt.inventory_status,
    sha256_prefix: receipt.sha256_prefix,
    file_size_bytes: receipt.file_size_bytes,
    created_at: receipt.created_at,
    downloaded_at: new Date().toISOString(),
  };
  const url = URL.createObjectURL(new Blob([JSON.stringify(safe, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${receipt.submission_id}_safe_receipt.json`;
  link.click();
  URL.revokeObjectURL(url);
}
