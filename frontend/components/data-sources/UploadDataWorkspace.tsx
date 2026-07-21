"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties, FormEvent, InputHTMLAttributes } from "react";
import { getDataProvider, isDemoMode } from "../../lib/data-provider/provider";
import type { IntakeCapabilities, IntakeSubmission } from "../../lib/data-provider/types";
import { compactNumber, label, safeText } from "../../lib/formatters";
import { resetDemoIntake } from "../../lib/data-provider/demo-review-store";
import { EmptyState, Panel, StageBadge, StatusBadge, workspaceStyles as ws } from "../ui/Primitives";
import styles from "./data-sources.module.css";

const utilitySystems = ["water", "wastewater", "stormwater", "telecom", "electric", "gas", "shared_reference", "mixed", "unknown", "review_required"];
const sensitivities = ["public", "internal", "restricted", "highly_restricted"];
const defaultMaxDirectoryFiles = 50000;
type PackageMode = "file" | "directory";
type DirectoryInputProps = InputHTMLAttributes<HTMLInputElement> & { webkitdirectory?: string; directory?: string };
type DirectorySummary = { rootName: string; fileCount: number; totalBytes: number; valid: boolean; errors: string[]; relativePaths: string[] };

export function UploadDataWorkspace() {
  const provider = getDataProvider();
  const [capabilities, setCapabilities] = useState<IntakeCapabilities | null>(null);
  const [packageMode, setPackageMode] = useState<PackageMode>("file");
  const [files, setFiles] = useState<File[]>([]);
  const [directoryFiles, setDirectoryFiles] = useState<File[]>([]);
  const [status, setStatus] = useState("queued");
  const [message, setMessage] = useState("");
  const [receipts, setReceipts] = useState<IntakeSubmission[]>([]);
  const [uploadProgress, setUploadProgress] = useState(0);
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

  const maxDirectoryFiles = Number(process.env.NEXT_PUBLIC_UTILITY_UPLOAD_MAX_FILES ?? capabilities?.maximum_upload_files ?? defaultMaxDirectoryFiles);
  const maxUploadBytes = Number(capabilities?.maximum_upload_bytes ?? 1073741824);
  const preliminary = useMemo(() => files.map((file) => ({ file, format: detectFormat(file.name), valid: Boolean(detectFormat(file.name)) })), [files]);
  const directorySummary = useMemo(() => validateDirectorySelection(directoryFiles, maxDirectoryFiles, maxUploadBytes), [directoryFiles, maxDirectoryFiles, maxUploadBytes]);
  const hasSelection = packageMode === "directory" ? directorySummary.valid : files.length > 0;
  const canSubmit = (hasSelection || isDemoMode) && form.submission_name && form.source_owner && form.source_description && form.authorization_confirmed;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit) {
      setMessage("Complete source metadata and authorization before upload.");
      return;
    }
    setReceipts([]);
    setUploadProgress(0);
    try {
      const nextReceipts: IntakeSubmission[] = [];
      if (packageMode === "directory") {
        if (!directorySummary.valid) {
          setStatus("failed");
          setMessage(directorySummary.errors[0] ?? "Select one complete .gdb folder.");
          return;
        }
        setStatus("validating_structure");
        const response = await provider.createDirectoryIntakeSubmission(directoryFormData(directorySummary), (progress) => {
          setUploadProgress(progress.percent);
          setStatus("uploading_files");
        });
        nextReceipts.push(...response.submissions);
      } else {
        setStatus("uploading");
        const targets = isDemoMode && files.length === 0 ? [null] : files;
        for (const file of targets) {
          const body = formData(file, false);
          const response = await provider.createIntakeSubmission(body);
          nextReceipts.push(...response.submissions);
        }
      }
      setStatus("registered_raw");
      setReceipts(nextReceipts);
      setMessage(isDemoMode ? "Demo mode does not upload or inspect your folder. The workflow is simulated with synthetic results." : "Package registered in local Raw storage.");
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
    setMessage("Demo mode does not upload or inspect your folder. The workflow is simulated with synthetic results.");
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

  function directoryFormData(summary: DirectorySummary) {
    const data = formData(null, false);
    data.set("package_mode", "directory");
    data.set("directory_root", summary.rootName);
    data.set("directory_file_count", String(summary.fileCount));
    data.set("directory_size", String(summary.totalBytes));
    data.delete("files");
    for (const file of directoryFiles) data.append("files", file, file.name);
    for (const relativePath of summary.relativePaths) data.append("relative_paths", relativePath);
    data.set("submission_name", form.submission_name || summary.rootName);
    return data;
  }

  function onFileSelect(selected: FileList | null) {
    setFiles(Array.from(selected ?? []));
    setDirectoryFiles([]);
    setStatus("queued");
    setReceipts([]);
  }

  function onDirectorySelect(selected: FileList | null) {
    setDirectoryFiles(Array.from(selected ?? []));
    setFiles([]);
    setStatus("folder_selected");
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
          {isDemoMode ? <button className={`${ws.button} ${ws.buttonPrimary}`} onClick={loadSyntheticSample}>Load Synthetic Mixed FileGDB</button> : null}
          {isDemoMode ? <button className={ws.button} onClick={() => { resetDemoIntake(); setReceipts([]); setMessage("Demo intake reset."); }}>Reset Demo Intake</button> : null}
          <Link className={ws.button} href="/data-sources?stage=raw">View Raw Stage</Link>
        </div>
      </Panel>

      <form className={styles.uploadGrid} onSubmit={submit}>
        <div className={ws.workspace}>
          <Panel title="Step 1 - Select Package" description="Choose a packaged file or one complete FileGDB folder. Each selection becomes one logical Raw source package.">
            <fieldset className={styles.modeSelector}>
              <legend>Package Type</legend>
              <label><input type="radio" checked={packageMode === "file"} onChange={() => setPackageMode("file")} /> Choose Package File</label>
              <label><input type="radio" checked={packageMode === "directory"} onChange={() => setPackageMode("directory")} /> Choose FileGDB Folder</label>
            </fieldset>
            {packageMode === "file" ? (
              <>
                <label
                  className={styles.dropZone}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={(event) => {
                    event.preventDefault();
                    onFileSelect(event.dataTransfer.files);
                  }}
                >
                  <calcite-icon icon="upload" scale="l" />
                  <strong>Choose Package File</strong>
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
              </>
            ) : (
              <>
                <label className={styles.dropZone}>
                  <calcite-icon icon="folderOpen" scale="l" />
                  <strong>Choose FileGDB Folder</strong>
                  <span className={styles.muted}>Select the complete .gdb folder. All internal geodatabase files will be included automatically.</span>
                  <DirectoryInput onChange={onDirectorySelect} />
                </label>
                {isDemoMode ? <p className={styles.muted}>Demo mode does not upload or inspect your folder. The workflow is simulated with synthetic results.</p> : <p className={styles.muted}>The folder remains local to this workstation and is sent only to the configured local backend.</p>}
                <DirectorySummaryView summary={directorySummary} maxFiles={maxDirectoryFiles} maxBytes={maxUploadBytes} />
              </>
            )}
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
              <div><dt>Package count</dt><dd>{packageMode === "directory" ? compactNumber(directorySummary.valid ? 1 : 0) : compactNumber(files.length)}</dd></div>
              <div><dt>FileGDB files</dt><dd>{packageMode === "directory" ? compactNumber(directorySummary.fileCount) : "Not folder mode"}</dd></div>
              <div><dt>Authorization</dt><dd>{form.authorization_confirmed ? "Confirmed" : "Required"}</dd></div>
            </dl>
          </Panel>

          <Panel title="Step 4 - Upload" description="No automatic staging, repair, publication, standardization, curation, or export occurs.">
            <div className={styles.progressTrack}><div className={styles.progressFill} style={{ "--progress-width": packageMode === "directory" && uploadProgress ? `${uploadProgress}%` : progress(status) } as CSSProperties} /></div>
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

function DirectoryInput({ onChange }: { onChange: (files: FileList | null) => void }) {
  const props: DirectoryInputProps = {
    type: "file",
    multiple: true,
    webkitdirectory: "",
    directory: "",
    onChange: (event) => onChange(event.currentTarget.files),
  };
  return <input {...props} />;
}

function DirectorySummaryView({ summary, maxFiles, maxBytes }: { summary: DirectorySummary; maxFiles: number; maxBytes: number }) {
  if (!summary.fileCount) {
    return <EmptyState title="No FileGDB folder selected" message="Use the folder picker to select one complete .gdb directory." />;
  }
  return (
    <div className={styles.packageSummary}>
      <dl className={styles.metadataList}>
        <div><dt>Root folder</dt><dd>{summary.rootName || "Unavailable"}</dd></div>
        <div><dt>Selected files</dt><dd>{compactNumber(summary.fileCount)} of {compactNumber(maxFiles)} allowed</dd></div>
        <div><dt>Aggregate size</dt><dd>{compactNumber(summary.totalBytes)} of {compactNumber(maxBytes)} bytes allowed</dd></div>
        <div><dt>Detected package type</dt><dd>{summary.rootName.toLowerCase().endsWith(".gdb") ? "File geodatabase folder" : "Unsupported folder"}</dd></div>
        <div><dt>Preliminary validation</dt><dd>{summary.valid ? "Passed browser precheck" : summary.errors.join("; ")}</dd></div>
      </dl>
      <details>
        <summary>View Package Contents</summary>
        <ol className={styles.contentsList}>
          {summary.relativePaths.slice(0, 25).map((path) => <li key={path}>{path}</li>)}
        </ol>
        {summary.relativePaths.length > 25 ? <p className={styles.muted}>Showing first 25 of {compactNumber(summary.relativePaths.length)} files.</p> : null}
      </details>
    </div>
  );
}

function validateDirectorySelection(files: File[], maxFiles: number, maxBytes: number): DirectorySummary {
  const errors: string[] = [];
  const relativePaths = files.map((file) => String((file as File & { webkitRelativePath?: string }).webkitRelativePath || ""));
  const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
  const roots = new Set<string>();
  const seen = new Set<string>();
  if (!files.length) return { rootName: "", fileCount: 0, totalBytes: 0, valid: false, errors: ["Select one complete .gdb folder."], relativePaths: [] };
  if (files.length > maxFiles) errors.push("File count exceeds configured limit.");
  if (totalBytes > maxBytes) errors.push("Aggregate size exceeds configured limit.");
  for (const relativePath of relativePaths) {
    const normalized = relativePath.replaceAll("\\", "/");
    const parts = normalized.split("/");
    if (!normalized) errors.push("A selected file is missing a browser relative path.");
    if (normalized.startsWith("/") || normalized.startsWith("//") || /^[A-Za-z]:\//.test(normalized)) errors.push("A selected file has an absolute path.");
    if (parts.some((part) => !part || part === "." || part === "..")) errors.push("A selected file has an unsafe relative path.");
    if (parts.length < 2) errors.push("All files must be inside the selected .gdb root.");
    if (seen.has(normalized)) errors.push("Duplicate relative path detected.");
    seen.add(normalized);
    if (parts[0]) roots.add(parts[0]);
  }
  const rootName = roots.size === 1 ? [...roots][0] : "";
  if (roots.size > 1) errors.push("Select exactly one top-level folder.");
  if (rootName && !rootName.toLowerCase().endsWith(".gdb")) errors.push("Top-level folder must end in .gdb.");
  return { rootName, fileCount: files.length, totalBytes, valid: errors.length === 0, errors: [...new Set(errors)], relativePaths };
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
