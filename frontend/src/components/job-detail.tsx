"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { DeleteJobButton } from "@/components/delete-job-button";
import { JobStatusBadge } from "@/components/job-status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { formatJobDuration, formatTimestamp } from "@/lib/format";
import type { Job } from "@/lib/types";
import { DownloadIcon, TriangleAlertIcon } from "lucide-react";

const POLL_INTERVAL_MS = 3000;
const ACTIVE_STATUSES = new Set(["queued", "processing"]);

export function JobDetail({ initialJob }: { initialJob: Job }) {
  const router = useRouter();
  const [job, setJob] = useState(initialJob);

  useEffect(() => {
    if (!ACTIVE_STATUSES.has(job.status)) return;
    const interval = setInterval(async () => {
      try {
        const response = await fetch(`/api/jobs/${job.id}`, { cache: "no-store" });
        if (response.ok) setJob(await response.json());
      } catch {
        // Transient network error; the next poll will retry.
      }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [job.id, job.status]);

  const processedIn = formatJobDuration(job.started_at, job.completed_at);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-medium">{job.original_filename}</h1>
          <p className="text-sm text-muted-foreground">Job {job.id}</p>
        </div>
        <div className="flex items-center gap-2">
          <JobStatusBadge status={job.status} />
          <DeleteJobButton
            jobId={job.id}
            filename={job.original_filename}
            onDeleted={() => router.push("/")}
          />
        </div>
      </div>

      {job.status === "failed" && (
        <Alert variant="destructive">
          <TriangleAlertIcon />
          <AlertTitle>Transcription failed</AlertTitle>
          <AlertDescription>{job.error}</AlertDescription>
        </Alert>
      )}

      {ACTIVE_STATUSES.has(job.status) && (
        <Card>
          <CardContent className="flex items-center gap-3 py-6">
            <Spinner />
            <span className="text-sm text-muted-foreground">
              {job.status === "queued"
                ? "Waiting for the GPU worker to pick up this job…"
                : "Transcribing and identifying speakers — this can take a while for long recordings…"}
            </span>
          </CardContent>
        </Card>
      )}

      {job.status === "completed" && job.transcript && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Summary</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-5">
              <Summary label="Audio length" value={formatTimestamp(job.transcript.duration)} />
              {processedIn && <Summary label="Processed in" value={processedIn} />}
              <Summary label="Language" value={job.transcript.language.toUpperCase()} />
              <Summary label="Speakers" value={String(job.transcript.speakers.length)} />
              <Summary label="Model" value={job.transcript.models.transcription} />
            </CardContent>
          </Card>

          <div className="flex gap-2">
            <a
              href={`/api/jobs/${job.id}/download/docx`}
              download
              className={buttonVariants({ variant: "outline" })}
            >
              <DownloadIcon data-icon="inline-start" />
              Download DOCX
            </a>
            <a
              href={`/api/jobs/${job.id}/download/json`}
              download
              className={buttonVariants({ variant: "outline" })}
            >
              <DownloadIcon data-icon="inline-start" />
              Download JSON
            </a>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Transcript</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              {job.transcript.utterances.map((utterance, index) => (
                <div key={utterance.id ?? index} className="flex flex-col gap-1">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="font-mono">{formatTimestamp(utterance.start)}</span>
                    <Badge variant="secondary">{utterance.speaker}</Badge>
                  </div>
                  <p className="text-sm leading-relaxed">{utterance.text}</p>
                  {index < job.transcript!.utterances.length - 1 && <Separator className="mt-3" />}
                </div>
              ))}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function Summary({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
