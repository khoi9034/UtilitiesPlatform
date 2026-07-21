"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties, FormEvent, InputHTMLAttributes, ReactNode } from "react";
import { getDataProvider, isDemoMode } from "../../lib/data-provider/provider";
import type { IntakeCapabilities, IntakeSubmission, UploadProgress } from "../../lib/data-provider/types";
import { compactNumber, label, safeText } from "../../lib/formatters";
import { resetDemoIntake } from "../../lib/data-provider/demo-review-store";
import { EmptyState, Panel, StageBadge, StatusBadge, workspaceStyles as ws } from "../ui/Primitives";
import styles from "./data-sources.module.css";

const utilitySystems = ["water", "wastewater", "stormwater", "telecom", "electric", "gas", "shared_reference", "mixed", "unknown", "review_required"];
const sensitivities = ["public", "internal", "restricted", "highly_restricted"];
const defaultMaxDirectoryFiles = 50000;
const uploadSteps = ["Preparing submission", "Uploading files", "Validating package", "Calculating checksum", "Registering immutable Raw source", "Updating catalog and stage manifest", "Complete"];

type PackageMode = "file" | "directory";
type UploadState = "idle" | "preparing" | "uploading" | "validating" | "registering" | "complete" | "failed" | "duplicate_detected";
type DirectoryInputProps = InputHTMLAttributes<HTMLInputElement> & { webkitdirectory?: string; directory?: string };
type DirectorySummary = { rootName: string; fileCount: number; totalBytes: number; valid: boolean; errors: string[]; relativePaths: string[] };
type PackageReview = { name: string; format: string; fileCount: number; totalBytes: number; structureReady: boolean; sizeReady: boolean; fileCountReady: boolean; errors: string[] };

export function UploadDataWorkspace() {
  const provider = getDataProvider();
  const [capabilities, setCapabilities] = useState<IntakeCapabilities | null>(null);
  const [packageMode, setPackageMode] = useState<PackageMode>("file");
  const [files, setFiles] = useState<File[]>([]);
  const [directoryFiles, setDirectoryFiles] = useState<File[]>([]);
  const [demoSyntheticSelected, setDemoSyntheticSelected] = useState(false);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [message, setMessage] = useState("");
  const [receipts, setReceipts] = useState<IntakeSubmission[]>([]);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const [allowDuplicateVersion, setAllowDuplicateVersion] = useState(false);
  const [inspectionMessage, setInspectionMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
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
    provider.getIntakeCapabilities().then(setCapabilities).catch(() => setMessage("Backend unavailable. Start the local FastAPI service before uploading."));
  }, [provider]);

  const trimmedForm = useMemo(() => trimForm(form), [form]);
  const metadataErrors = useMemo(() => metadataValidation(trimmedForm), [trimmedForm]);
  const metadataReady = Object.keys(metadataErrors).length === 0;
  const maxDirectoryFiles = Number(process.env.NEXT_PUBLIC_UTILITY_UPLOAD_MAX_FILES ?? capabilities?.maximum_upload_files ?? defaultMaxDirectoryFiles);
  const maxUploadBytes = Number(capabilities?.maximum_upload_bytes ?? 1073741824);
  const preliminary = useMemo(() => files.map((file) => ({ file, format: detectFormat(file.name), valid: Boolean(detectFormat(file.name)) })), [files]);
  const directorySummary = useMemo(() => validateDirectorySelection(directoryFiles, maxDirectoryFiles, maxUploadBytes), [directoryFiles, maxDirectoryFiles, maxUploadBytes]);
  const packageReview = useMemo(() => selectedPackage({ packageMode, files, preliminary, directorySummary, demoSyntheticSelected, maxUploadBytes, maxDirectoryFiles }), [packageMode, files, preliminary, directorySummary, demoSyntheticSelected, maxUploadBytes, maxDirectoryFiles]);
  const backendReady = isDemoMode || Boolean(capabilities?.upload_enabled);
  const packageReady = packageReview.structureReady && packageReview.sizeReady && packageReview.fileCountReady;
  const hasPackageValidationProblems = Boolean(packageReview.name && !packageReady);
  const readyToUpload = metadataReady && packageReady && backendReady && !isSubmitting;
  const hasDraft = !receipts.length && !isSubmitting && (Object.values(trimmedForm).some((value) => typeof value === "string" && value) || files.length > 0 || directoryFiles.length > 0 || demoSyntheticSelected);
  const duplicateReceipt = receipts.find((receipt) => receipt.current_status === "duplicate_detected");

  useEffect(() => {
    if (!hasDraft) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [hasDraft]);

  async function submit(event?: FormEvent, registerDuplicate = false) {
    event?.preventDefault();
    if (isSubmitting) return;
    if (!readyToUpload && !registerDuplicate) {
      setMessage(actionLabel({ metadataReady, packageReady, hasPackageValidationProblems, backendReady, uploadState, isSubmitting }));
      return;
    }
    setReceipts([]);
    setMessage("");
    setInspectionMessage("");
    setUploadProgress(null);
    setIsSubmitting(true);
    setUploadState("preparing");
    try {
      const response = await sendSubmission(registerDuplicate);
      setUploadState("registering");
      const nextReceipts = response.submissions;
      setReceipts(nextReceipts);
      const duplicate = nextReceipts.find((receipt) => receipt.current_status === "duplicate_detected");
      if (duplicate) {
        setUploadState("duplicate_detected");
        setMessage("A matching package is already registered.");
        return;
      }
      setUploadState("complete");
      setMessage(isDemoMode ? "Synthetic Raw registration complete. No files were uploaded or inspected." : "Raw registration complete.");
      if (trimmedForm.run_inventory_after_upload) {
        await runSourceInspection(nextReceipts[0]);
      }
    } catch (error) {
      setUploadState("failed");
      setMessage(safeUploadError(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function sendSubmission(registerDuplicate: boolean) {
    setUploadState("uploading");
    if (demoSyntheticSelected) return provider.createIntakeSubmission(formData(null, true, registerDuplicate));
    if (packageMode === "directory") {
      return provider.createDirectoryIntakeSubmission(directoryFormData(directorySummary, registerDuplicate), (progress) => {
        setUploadProgress(progress);
        setUploadState("uploading");
      });
    }
    const response = await provider.createIntakeSubmission(formData(files[0] ?? null, false, registerDuplicate));
    setUploadState("validating");
    return response;
  }

  async function runSourceInspection(receipt: IntakeSubmission | undefined) {
    if (!receipt) return;
    setInspectionMessage("Source inspection starting...");
    const result = await provider.startSourceInspection(receipt.submission_id);
    const status = String(result.inspection_status ?? result.status ?? "requested");
    setInspectionMessage(`Source inspection ${label(status)}.`);
  }

  function formData(file: File | null, demoSample: boolean, registerDuplicate = false) {
    const data = new FormData();
    if (file) data.append("files", file, file.name);
    data.append("demo_sample", String(demoSample));
    for (const [key, value] of Object.entries(trimmedForm)) data.append(key, String(value));
    data.set("submission_name", trimmedForm.submission_name || (demoSample ? "Synthetic Mixed Utility Source" : "Metadata-Only Demo Source"));
    data.set("source_owner", trimmedForm.source_owner || "Synthetic Data Owner");
    data.set("source_description", trimmedForm.source_description || "Session-only portfolio demo intake simulation.");
    data.set("authorization_confirmed", String(trimmedForm.authorization_confirmed || demoSample));
    data.set("register_duplicate_as_version", String(registerDuplicate || allowDuplicateVersion));
    return data;
  }

  function directoryFormData(summary: DirectorySummary, registerDuplicate = false) {
    const data = formData(null, false, registerDuplicate);
    data.set("package_mode", "directory");
    data.set("directory_root", summary.rootName);
    data.set("directory_file_count", String(summary.fileCount));
    data.set("directory_size", String(summary.totalBytes));
    data.delete("files");
    for (const file of directoryFiles) data.append("files", file, file.name);
    for (const relativePath of summary.relativePaths) data.append("relative_paths", relativePath);
    data.set("submission_name", trimmedForm.submission_name || summary.rootName);
    return data;
  }

  function onFileSelect(selected: FileList | null) {
    setFiles(Array.from(selected ?? []));
    setDirectoryFiles([]);
    setDemoSyntheticSelected(false);
    setUploadState("idle");
    setReceipts([]);
    setMessage("");
  }

  function onDirectorySelect(selected: FileList | null) {
    setDirectoryFiles(Array.from(selected ?? []));
    setFiles([]);
    setDemoSyntheticSelected(false);
    setUploadState("idle");
    setReceipts([]);
    setMessage("");
  }

  function selectSyntheticDemoPackage() {
    setPackageMode("directory");
    setDemoSyntheticSelected(true);
    setFiles([]);
    setDirectoryFiles([]);
    setReceipts([]);
    setUploadState("idle");
    setMessage("Synthetic FileGDB selected locally. Not uploaded yet.");
  }

  function uploadAnother() {
    setFiles([]);
    setDirectoryFiles([]);
    setDemoSyntheticSelected(false);
    setReceipts([]);
    setUploadState("idle");
    setUploadProgress(null);
    setMessage("");
    setInspectionMessage("");
    setAllowDuplicateVersion(false);
  }

  return (
    <div className={ws.workspace}>
      <header className={ws.pageHeader}>
        <span className={ws.eyebrow}>{isDemoMode ? "PORTFOLIO DEMO INTAKE" : "LOCAL INTAKE"}</span>
        <h1>Upload Utility Data</h1>
        <p>Describe the source, select one package, review readiness, then register it as immutable Raw data.</p>
      </header>

      <Panel title={isDemoMode ? "Demo Mode" : "Local Storage Warning"} description={isDemoMode ? "No files are uploaded or inspected. The workflow uses temporary synthetic results." : "Uploads remain on this workstation and are not sent to the public portfolio demo."}>
        <div className={ws.buttonRow}>
          {isDemoMode ? <button className={ws.button} type="button" onClick={selectSyntheticDemoPackage}>Load Synthetic Mixed FileGDB</button> : null}
          {isDemoMode ? <button className={ws.button} type="button" onClick={() => { resetDemoIntake(); uploadAnother(); setMessage("Demo intake reset."); }}>Reset Demo Intake</button> : null}
          <Link className={ws.button} href="/data-sources?stage=raw">View Raw Stage</Link>
        </div>
      </Panel>

      {receipts.length && !duplicateReceipt ? (
        <SuccessReceipt receipts={receipts} packageReview={packageReview} inspectionMessage={inspectionMessage} onInspect={runSourceInspection} onAnother={uploadAnother} />
      ) : null}

      <form className={styles.guidedForm} onSubmit={(event) => submit(event)}>
        <Panel title="Source Information" description="Enter the source context before selecting or transmitting a package.">
          <div className={styles.formGrid}>
            <FieldError labelText="Submission name" error={metadataErrors.submission_name}><input className={ws.input} value={form.submission_name} onBlur={() => setForm(trimTextForm(form))} onChange={(event) => setForm({ ...form, submission_name: event.target.value })} /></FieldError>
            <FieldError labelText="Utility system" error={metadataErrors.utility_system}><select className={ws.select} value={form.utility_system} onChange={(event) => setForm({ ...form, utility_system: event.target.value })}>{utilitySystems.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></FieldError>
            <FieldError labelText="Source type" error={metadataErrors.source_type}><input className={ws.input} value={form.source_type} onBlur={() => setForm(trimTextForm(form))} onChange={(event) => setForm({ ...form, source_type: event.target.value })} /></FieldError>
            <FieldError labelText="Source owner" error={metadataErrors.source_owner}><input className={ws.input} value={form.source_owner} onBlur={() => setForm(trimTextForm(form))} onChange={(event) => setForm({ ...form, source_owner: event.target.value })} /></FieldError>
            <FieldError labelText="Sensitivity" error={metadataErrors.sensitivity_level}><select className={ws.select} value={form.sensitivity_level} onChange={(event) => setForm({ ...form, sensitivity_level: event.target.value })}>{sensitivities.map((item) => <option key={item} value={item}>{label(item)}</option>)}</select></FieldError>
            <FieldError labelText="Project ID"><input className={ws.input} value={form.project_id} onBlur={() => setForm(trimTextForm(form))} onChange={(event) => setForm({ ...form, project_id: event.target.value })} /></FieldError>
            <FieldError labelText="Submitted by" error={metadataErrors.submitted_by}><input className={ws.input} value={form.submitted_by} onBlur={() => setForm(trimTextForm(form))} onChange={(event) => setForm({ ...form, submitted_by: event.target.value })} /></FieldError>
            <FieldError labelText="Description" error={metadataErrors.source_description} fullWidth><textarea className={ws.input} value={form.source_description} onBlur={() => setForm(trimTextForm(form))} onChange={(event) => setForm({ ...form, source_description: event.target.value })} /></FieldError>
            <label className={`${styles.checkRow} ${styles.fullWidth}`}><input type="checkbox" checked={form.authorization_confirmed} onChange={(event) => setForm({ ...form, authorization_confirmed: event.target.checked })} /> I am authorized to store and analyze this source in the local Utilities Platform environment.</label>
            {metadataErrors.authorization_confirmed ? <span className={`${styles.fieldError} ${styles.fullWidth}`}>{metadataErrors.authorization_confirmed}</span> : null}
            <label className={`${styles.checkRow} ${styles.fullWidth}`}><input type="checkbox" checked={form.run_inventory_after_upload} onChange={(event) => setForm({ ...form, run_inventory_after_upload: event.target.checked })} /> Run source inspection after upload</label>
          </div>
        </Panel>

        <Panel title="Select Source Package" description="Selecting a file or folder does not upload it. The package is transmitted only after you press Upload to Local Raw.">
          <fieldset className={styles.modeSelector}>
            <legend>Package Type</legend>
            <label><input type="radio" checked={packageMode === "file"} onChange={() => setPackageMode("file")} /> Choose Package File</label>
            <label><input type="radio" checked={packageMode === "directory"} onChange={() => setPackageMode("directory")} /> Choose FileGDB Folder</label>
          </fieldset>
          {packageMode === "file" ? <PackageFilePicker preliminary={preliminary} onFileSelect={onFileSelect} onRemove={(file) => setFiles((current) => current.filter((item) => item !== file))} /> : <DirectoryPicker isSynthetic={demoSyntheticSelected} summary={directorySummary} maxFiles={maxDirectoryFiles} maxBytes={maxUploadBytes} onDirectorySelect={onDirectorySelect} />}
          <div className={styles.statusRow}><span className={styles.statusChip}>NOT UPLOADED</span><span className={styles.muted}>{packageReview.name ? "Package ready for review. Selected locally, not uploaded yet." : "No source package selected."}</span></div>
        </Panel>

        <Panel title="Review Submission" description="Ready to upload only appears when metadata, package, authorization, and local backend checks are satisfied.">
          <ReviewSummary form={trimmedForm} packageReview={packageReview} backendReady={backendReady} metadataReady={metadataReady} packageReady={packageReady} />
          <ValidationGroups metadataReady={metadataReady} packageReview={packageReview} authorizationReady={trimmedForm.authorization_confirmed} backendReady={backendReady} />
          {duplicateReceipt ? <DuplicateNotice receipt={duplicateReceipt} onCancel={() => { setReceipts([]); setUploadState("idle"); setMessage(""); }} onRegister={() => { setAllowDuplicateVersion(true); void submit(undefined, true); }} /> : null}
          {uploadState !== "idle" ? <ProgressPanel state={uploadState} progress={uploadProgress} packageReview={packageReview} /> : null}
          {message ? <p className={uploadState === "failed" ? styles.errorBanner : styles.muted}>{message}</p> : null}
          <div className={styles.actionBar}>
            <div><strong>{readyToUpload ? "Ready to upload" : actionLabel({ metadataReady, packageReady, hasPackageValidationProblems, backendReady, uploadState, isSubmitting })}</strong><p className={styles.muted}>{isDemoMode ? "Demo mode stores a temporary synthetic receipt only." : "The package goes only to local Raw storage."}</p></div>
            <button className={`${ws.button} ${ws.buttonPrimary}`} type="submit" disabled={!readyToUpload || isSubmitting}>{isDemoMode ? "Simulate Raw Registration" : actionLabel({ metadataReady, packageReady, hasPackageValidationProblems, backendReady, uploadState, isSubmitting, readyText: "Upload to Local Raw" })}</button>
          </div>
        </Panel>
      </form>
    </div>
  );
}

function FieldError({ labelText, error, fullWidth, children }: { labelText: string; error?: string; fullWidth?: boolean; children: ReactNode }) {
  return <label className={fullWidth ? styles.fullWidth : undefined}>{labelText}{children}{error ? <span className={styles.fieldError}>{error}</span> : null}</label>;
}

function PackageFilePicker({ preliminary, onFileSelect, onRemove }: { preliminary: { file: File; format: string; valid: boolean }[]; onFileSelect: (files: FileList | null) => void; onRemove: (file: File) => void }) {
  return (
    <>
      <label className={styles.dropZone} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); onFileSelect(event.dataTransfer.files); }}>
        <calcite-icon icon="upload" scale="l" />
        <strong>Select approved package file</strong>
        <span className={styles.muted}>ZIP shapefiles or geodatabases, DWG, DXF, GPKG, CSV, XLSX, or PDF.</span>
        <input type="file" onChange={(event) => onFileSelect(event.target.files)} />
      </label>
      <div className={styles.fileList}>
        {preliminary.length ? preliminary.map(({ file, format, valid }) => (
          <div className={styles.fileItem} key={`${file.name}-${file.size}`}>
            <strong>{file.name}</strong>
            <span className={styles.muted}>{compactNumber(file.size)} bytes - {format ? label(format) : "Unsupported"} - {valid ? "Preliminary format accepted" : "Rejected by browser precheck"}</span>
            <button className={ws.button} type="button" onClick={() => onRemove(file)}>Remove</button>
          </div>
        )) : <EmptyState title="No package selected" message="Select one approved local source package." />}
      </div>
    </>
  );
}

function DirectoryPicker({ isSynthetic, summary, maxFiles, maxBytes, onDirectorySelect }: { isSynthetic: boolean; summary: DirectorySummary; maxFiles: number; maxBytes: number; onDirectorySelect: (files: FileList | null) => void }) {
  return (
    <>
      <label className={styles.dropZone}>
        <calcite-icon icon="folderOpen" scale="l" />
        <strong>Select complete .gdb folder</strong>
        <span className={styles.muted}>Select the complete .gdb folder. All internal geodatabase files will be included automatically.</span>
        <DirectoryInput onChange={onDirectorySelect} />
      </label>
      {isDemoMode ? <p className={styles.muted}>Demo mode does not upload or inspect your folder. The workflow is simulated with synthetic results.</p> : <p className={styles.muted}>The folder remains local to this workstation and is sent only to the configured local backend.</p>}
      {isSynthetic ? <DemoPackageSummary /> : <DirectorySummaryView summary={summary} maxFiles={maxFiles} maxBytes={maxBytes} />}
    </>
  );
}

function DirectoryInput({ onChange }: { onChange: (files: FileList | null) => void }) {
  const props: DirectoryInputProps = { type: "file", multiple: true, webkitdirectory: "", directory: "", onChange: (event) => onChange(event.currentTarget.files) };
  return <input {...props} />;
}

function DirectorySummaryView({ summary, maxFiles, maxBytes }: { summary: DirectorySummary; maxFiles: number; maxBytes: number }) {
  if (!summary.fileCount) return <EmptyState title="No FileGDB folder selected" message="Use the folder picker to select one complete .gdb directory." />;
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
        <ol className={styles.contentsList}>{summary.relativePaths.slice(0, 25).map((path) => <li key={path}>{path}</li>)}</ol>
        {summary.relativePaths.length > 25 ? <p className={styles.muted}>Showing first 25 of {compactNumber(summary.relativePaths.length)} files.</p> : null}
      </details>
    </div>
  );
}

function DemoPackageSummary() {
  return (
    <div className={styles.packageSummary}>
      <dl className={styles.metadataList}>
        <div><dt>Root folder</dt><dd>Sample_Mixed_Utility_Source.gdb</dd></div>
        <div><dt>Selected files</dt><dd>Synthetic demo package</dd></div>
        <div><dt>Aggregate size</dt><dd>1.8M bytes</dd></div>
        <div><dt>Detected package type</dt><dd>File geodatabase folder</dd></div>
        <div><dt>Preliminary validation</dt><dd>Passed demo precheck</dd></div>
      </dl>
    </div>
  );
}

function ReviewSummary({ form, packageReview, backendReady, metadataReady, packageReady }: { form: ReturnType<typeof trimForm>; packageReview: PackageReview; backendReady: boolean; metadataReady: boolean; packageReady: boolean }) {
  return (
    <dl className={styles.reviewGrid}>
      <div><dt>Submission name</dt><dd>{form.submission_name || "Required"}</dd></div>
      <div><dt>Utility system</dt><dd>{label(form.utility_system)}</dd></div>
      <div><dt>Source owner</dt><dd>{form.source_owner || "Required"}</dd></div>
      <div><dt>Sensitivity</dt><dd>{label(form.sensitivity_level)}</dd></div>
      <div><dt>Package name</dt><dd>{packageReview.name || "Select a source package"}</dd></div>
      <div><dt>Package format</dt><dd>{packageReview.format || "Pending"}</dd></div>
      <div><dt>File count</dt><dd>{compactNumber(packageReview.fileCount)}</dd></div>
      <div><dt>Total size</dt><dd>{compactNumber(packageReview.totalBytes)} bytes</dd></div>
      <div><dt>Authorization</dt><dd>{form.authorization_confirmed ? "Confirmed" : "Required"}</dd></div>
      <div><dt>Automatic inspection</dt><dd>{form.run_inventory_after_upload ? "Run after upload" : "Manual next action"}</dd></div>
      <div><dt>Local backend readiness</dt><dd>{backendReady ? "Ready" : "Unavailable"}</dd></div>
      <div><dt>Upload readiness</dt><dd>{metadataReady && packageReady && backendReady ? "Ready to upload" : "Not ready"}</dd></div>
    </dl>
  );
}

function ValidationGroups({ metadataReady, packageReview, authorizationReady, backendReady }: { metadataReady: boolean; packageReview: PackageReview; authorizationReady: boolean; backendReady: boolean }) {
  const groups = [
    ["Metadata", metadataReady],
    ["Package structure", packageReview.structureReady],
    ["Size", packageReview.sizeReady],
    ["File count", packageReview.fileCountReady],
    ["Authorization", authorizationReady],
    ["Local backend readiness", backendReady],
  ] as const;
  return <div className={styles.validationGrid}>{groups.map(([name, ok]) => <span className={ok ? styles.goodChip : styles.warnChip} key={name}>{name}: {ok ? "OK" : "Needs attention"}</span>)}</div>;
}

function ProgressPanel({ state, progress, packageReview }: { state: UploadState; progress: UploadProgress | null; packageReview: PackageReview }) {
  const index = state === "complete" ? uploadSteps.length - 1 : state === "registering" ? 4 : state === "validating" ? 2 : state === "uploading" ? 1 : state === "preparing" ? 0 : 0;
  return (
    <div className={styles.progressPanel}>
      <strong>{uploadSteps[index]}</strong>
      <div className={styles.progressTrack}><div className={styles.progressFill} style={{ "--progress-width": progress ? `${progress.percent}%` : `${Math.max(8, Math.round((index / (uploadSteps.length - 1)) * 100))}%` } as CSSProperties} /></div>
      <dl className={styles.metadataList}>
        <div><dt>Files transferred</dt><dd>{progress ? "Browser upload in progress" : state === "complete" ? compactNumber(packageReview.fileCount) : "Pending"}</dd></div>
        <div><dt>Total files</dt><dd>{compactNumber(packageReview.fileCount)}</dd></div>
        <div><dt>Bytes transferred</dt><dd>{progress ? compactNumber(progress.loaded) : "Exact byte progress unavailable"}</dd></div>
        <div><dt>Total bytes</dt><dd>{progress ? compactNumber(progress.total) : `${compactNumber(packageReview.totalBytes)} bytes`}</dd></div>
        <div><dt>Percentage</dt><dd>{progress ? `${progress.percent}%` : "Processing stage only"}</dd></div>
      </dl>
    </div>
  );
}

function DuplicateNotice({ receipt, onCancel, onRegister }: { receipt: IntakeSubmission; onCancel: () => void; onRegister: () => void }) {
  return (
    <div className={styles.errorBanner}>
      <strong>A matching package is already registered.</strong>
      <p>Prior submission ID: {String(receipt.duplicate_of_submission_id ?? "available in registry")}</p>
      <div className={ws.buttonRow}>
        <button className={ws.button} type="button" onClick={onCancel}>Cancel</button>
        <button className={`${ws.button} ${ws.buttonPrimary}`} type="button" onClick={onRegister}>Register as new version</button>
      </div>
    </div>
  );
}

function SuccessReceipt({ receipts, packageReview, inspectionMessage, onInspect, onAnother }: { receipts: IntakeSubmission[]; packageReview: PackageReview; inspectionMessage: string; onInspect: (receipt: IntakeSubmission) => void; onAnother: () => void }) {
  return (
    <Panel title="Raw Registration Complete" description="Safe receipt only; absolute local paths are not included.">
      <div className={styles.receiptList}>
        {receipts.map((receipt) => (
          <div className={styles.successReceipt} key={receipt.submission_id}>
            <span className={styles.statusChip}>RAW REGISTERED</span>
            <dl className={styles.reviewGrid}>
              <div><dt>Submission ID</dt><dd>{receipt.submission_id}</dd></div>
              <div><dt>Submission name</dt><dd>{receipt.submission_name}</dd></div>
              <div><dt>Safe original package name</dt><dd>{receipt.original_filename}</dd></div>
              <div><dt>Source format</dt><dd>{label(receipt.source_format)}</dd></div>
              <div><dt>Utility-system context</dt><dd>{label(receipt.utility_system)}</dd></div>
              <div><dt>File count</dt><dd>{compactNumber(packageReview.fileCount || fileCount(receipt))}</dd></div>
              <div><dt>Total size</dt><dd>{compactNumber(Number(receipt.file_size_bytes ?? packageReview.totalBytes))} bytes</dd></div>
              <div><dt>Package SHA-256</dt><dd>{safeText(receipt.sha256_prefix)}</dd></div>
              <div><dt>Current stage</dt><dd>{label(receipt.current_stage || "raw")}</dd></div>
              <div><dt>Registration status</dt><dd><StageBadge value={receipt.current_status} /></dd></div>
              <div><dt>Inspection status</dt><dd><StatusBadge value={receipt.inventory_status} /></dd></div>
              <div><dt>Created time</dt><dd>{String(receipt.created_at ?? "")}</dd></div>
              <div><dt>Next required action</dt><dd>{receipt.next_required_action}</dd></div>
            </dl>
            {inspectionMessage ? <p className={styles.muted}>{inspectionMessage}</p> : null}
            <div className={ws.buttonRow}>
              <Link className={ws.button} href={`/data-sources/submission?id=${encodeURIComponent(receipt.submission_id)}`}>View Submission</Link>
              <button className={`${ws.button} ${ws.buttonPrimary}`} type="button" onClick={() => onInspect(receipt)}>Run Source Inspection</button>
              <Link className={ws.button} href="/data-sources?stage=raw">View in Raw Stage</Link>
              <button className={ws.button} type="button" onClick={onAnother}>Upload Another Package</button>
              <button className={ws.button} type="button" onClick={() => downloadReceipt(receipt)}>Download Safe Receipt</button>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function selectedPackage(args: { packageMode: PackageMode; files: File[]; preliminary: { file: File; format: string; valid: boolean }[]; directorySummary: DirectorySummary; demoSyntheticSelected: boolean; maxUploadBytes: number; maxDirectoryFiles: number }): PackageReview {
  if (args.demoSyntheticSelected) return { name: "Sample_Mixed_Utility_Source.gdb", format: "file_geodatabase", fileCount: 1, totalBytes: 1843200, structureReady: true, sizeReady: true, fileCountReady: true, errors: [] };
  if (args.packageMode === "directory") {
    return { name: args.directorySummary.rootName, format: args.directorySummary.rootName ? "file_geodatabase" : "", fileCount: args.directorySummary.fileCount, totalBytes: args.directorySummary.totalBytes, structureReady: args.directorySummary.valid, sizeReady: args.directorySummary.totalBytes <= args.maxUploadBytes, fileCountReady: args.directorySummary.fileCount <= args.maxDirectoryFiles, errors: args.directorySummary.errors };
  }
  const file = args.files[0];
  const invalid = args.preliminary.filter((item) => !item.valid);
  const totalBytes = args.files.reduce((sum, item) => sum + item.size, 0);
  return { name: file?.name ?? "", format: args.preliminary[0]?.format ?? "", fileCount: args.files.length, totalBytes, structureReady: args.files.length > 0 && invalid.length === 0, sizeReady: totalBytes <= args.maxUploadBytes, fileCountReady: args.files.length > 0, errors: invalid.map((item) => `${item.file.name} is unsupported.`) };
}

function metadataValidation(form: ReturnType<typeof trimForm>) {
  const errors: Record<string, string> = {};
  for (const field of ["submission_name", "utility_system", "source_type", "source_owner", "source_description", "sensitivity_level", "submitted_by"] as const) {
    if (!String(form[field] ?? "").trim()) errors[field] = "Required";
  }
  if (!form.authorization_confirmed) errors.authorization_confirmed = "Authorization confirmation is required.";
  return errors;
}

function trimForm(form: Record<string, string | boolean>) {
  return Object.fromEntries(Object.entries(form).map(([key, value]) => [key, typeof value === "string" ? value.trim() : value])) as {
    submission_name: string; utility_system: string; source_type: string; source_owner: string; source_description: string; sensitivity_level: string; project_id: string; submitted_by: string; authorization_confirmed: boolean; run_inventory_after_upload: boolean;
  };
}

function trimTextForm<T extends Record<string, string | boolean>>(form: T): T {
  return trimForm(form) as unknown as T;
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

function actionLabel(args: { metadataReady: boolean; packageReady: boolean; hasPackageValidationProblems?: boolean; backendReady: boolean; uploadState: UploadState; isSubmitting: boolean; readyText?: string }) {
  if (args.uploadState === "complete") return "Complete";
  if (args.uploadState === "failed") return "Failed - Retry";
  if (args.isSubmitting && args.uploadState === "preparing") return "Preparing submission";
  if (args.isSubmitting && args.uploadState === "uploading") return "Uploading...";
  if (args.isSubmitting && args.uploadState === "validating") return "Validating package...";
  if (args.isSubmitting && args.uploadState === "registering") return "Registering Raw source...";
  if (!args.metadataReady) return "Complete required information";
  if (!args.packageReady) return args.hasPackageValidationProblems ? "Fix validation problems" : "Select a source package";
  if (!args.backendReady) return "Local backend unavailable";
  return args.readyText ?? "Ready to upload";
}

function safeUploadError(error: unknown) {
  const text = error instanceof Error ? error.message : "Upload failed safely.";
  if (/413|too large|size/i.test(text)) return "Package too large. Reduce package size or increase the configured upload limit.";
  if (/count|too many/i.test(text)) return "Too many files. Select one complete FileGDB within the configured file-count limit.";
  if (/duplicate/i.test(text)) return "A matching package is already registered.";
  if (/fetch|network|failed|0 /.test(text)) return "Backend unavailable or upload interrupted. Confirm the local backend is running, then retry.";
  if (/gdb|structure|path/i.test(text)) return `Invalid FileGDB structure. ${text}`;
  if (/authorization/i.test(text)) return "Authorization missing. Confirm authorization before upload.";
  return `Registration failed. ${text}`;
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

function fileCount(receipt: IntakeSubmission) {
  const files = receipt.files;
  return Array.isArray(files) ? files.length : 1;
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
