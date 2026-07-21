"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getDataProvider, isDemoMode } from "../../lib/data-provider/provider";
import type { IntakeEvent, IntakeSubmission } from "../../lib/data-provider/types";
import { compactNumber, label, safeText, shortDate } from "../../lib/formatters";
import { EmptyState, LoadingSkeleton, Panel, StageBadge, StatusBadge, workspaceStyles as ws } from "../ui/Primitives";
import styles from "./data-sources.module.css";

export function SubmissionWorkspace() {
  const provider = getDataProvider();
  const [submissionId] = useState(() => initialSubmissionId());
  const [submission, setSubmission] = useState<IntakeSubmission | null>(null);
  const [events, setEvents] = useState<IntakeEvent[]>([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(Boolean(submissionId));

  useEffect(() => {
    if (!submissionId) return;
    Promise.allSettled([provider.getIntakeSubmission(submissionId), provider.getIntakeEvents(submissionId)]).then(([submissionResult, eventResult]) => {
      if (submissionResult.status === "fulfilled") setSubmission(submissionResult.value);
      if (eventResult.status === "fulfilled") setEvents(eventResult.value.events);
      if (submissionResult.status === "rejected") setMessage("Submission is unavailable.");
      setLoading(false);
    });
  }, [provider, submissionId]);

  async function runInventory() {
    if (!submissionId) return;
    await provider.startIntakeInventory(submissionId);
    const refreshed = await provider.getIntakeSubmission(submissionId);
    setSubmission(refreshed);
    setMessage("Inventory action completed. Staging still requires explicit human approval.");
  }

  if (loading) {
    return (
      <div className={ws.workspace}>
        <PageIntro />
        <LoadingSkeleton />
      </div>
    );
  }

  if (!submission) {
    return (
      <div className={ws.workspace}>
        <PageIntro />
        <EmptyState title="Submission not found" message={message || "Open a submission from the Raw stage or upload receipt."} />
      </div>
    );
  }

  return (
    <div className={ws.workspace}>
      <PageIntro />
      {message ? <p className={styles.muted}>{message}</p> : null}
      <section className={ws.grid12}>
        <div className={ws.span3}><Panel title="Status" description="Current intake state."><StageBadge value={submission.current_status} /></Panel></div>
        <div className={ws.span3}><Panel title="Inventory" description="Inspection copy only."><StatusBadge value={submission.inventory_status} /></Panel></div>
        <div className={ws.span3}><Panel title="Classification" description="Human review may be required."><StatusBadge value={submission.classification_status} /></Panel></div>
        <div className={ws.span3}><Panel title="Staging" description="No automatic staging."><StatusBadge value={submission.staging_status} /></Panel></div>
      </section>

      <section className={styles.layout}>
        <Panel title="Submission Identity" description="Safe metadata; no full local paths.">
          <dl className={styles.metadataList}>
            <div><dt>Submission ID</dt><dd className="technical">{submission.submission_id}</dd></div>
            <div><dt>Name</dt><dd>{submission.submission_name}</dd></div>
            <div><dt>Original filename</dt><dd>{submission.original_filename}</dd></div>
            <div><dt>Utility system</dt><dd>{label(submission.utility_system)}</dd></div>
            <div><dt>Source format</dt><dd>{label(submission.source_format)}</dd></div>
            <div><dt>Sensitivity</dt><dd><StatusBadge value={submission.sensitivity_level} /></dd></div>
            <div><dt>Size</dt><dd>{compactNumber(submission.file_size_bytes as number)} bytes</dd></div>
            <div><dt>SHA-256</dt><dd>{safeText(submission.sha256_prefix)}...</dd></div>
            <div><dt>Created</dt><dd>{shortDate(submission.created_at as string)}</dd></div>
            <div><dt>Next action</dt><dd>{submission.next_required_action}</dd></div>
          </dl>
        </Panel>

        <Panel title="Package Files" description="Safe filenames and package roles only.">
          {Array.isArray(submission.files) && submission.files.length ? (
            <div className={styles.fileList}>
              {submission.files.map((file) => (
                <div className={styles.fileItem} key={`${file.relative_role}-${file.safe_filename}`}>
                  <strong>{String(file.safe_filename)}</strong>
                  <span className={styles.muted}>{label(String(file.relative_role))} - {compactNumber(Number(file.size_bytes ?? 0))} bytes - {label(String(file.validation_status))}</span>
                </div>
              ))}
            </div>
          ) : <EmptyState title="No file rows" message="No safe file inventory has been recorded." />}
        </Panel>

        <Panel title="Timeline" description="Immutable intake events.">
          <div className={styles.timeline}>
            {events.length ? events.map((event) => (
              <div className={styles.timelineItem} key={event.event_id}>
                <strong>{label(event.event_type)}</strong>
                <span className={styles.muted}>{event.message}</span>
                <span className={styles.muted}>{shortDate(event.created_at)}</span>
              </div>
            )) : <EmptyState title="No events" message="No event history is available for this submission." />}
          </div>
        </Panel>
      </section>

      <Panel title="Actions" description={isDemoMode ? "Demo actions stay in sessionStorage." : "No destructive actions are available in V1."}>
        <div className={ws.buttonRow}>
          <Link className={ws.button} href="/data-sources?stage=raw">View Raw Stage</Link>
          <button className={ws.button} onClick={runInventory}>Run Inventory</button>
          <Link className={ws.button} href="/data-sources/upload">Upload Another Package</Link>
        </div>
      </Panel>
    </div>
  );
}

function PageIntro() {
  return (
    <header className={ws.pageHeader}>
      <span className={ws.eyebrow}>{isDemoMode ? "PORTFOLIO DEMO" : "LOCAL INTAKE"}</span>
      <h1>Submission Detail</h1>
      <p>Review intake identity, validation, inventory, lineage, blockers, next action, and event history without exposing workstation paths.</p>
    </header>
  );
}

function initialSubmissionId() {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get("id") ?? "";
}
