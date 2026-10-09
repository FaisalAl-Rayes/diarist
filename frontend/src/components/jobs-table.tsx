"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { DeleteJobButton } from "@/components/delete-job-button";
import { JobStatusBadge } from "@/components/job-status-badge";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatJobDuration, formatRelativeTime } from "@/lib/format";
import type { Job } from "@/lib/types";
import { AudioLinesIcon } from "lucide-react";

const POLL_INTERVAL_MS = 4000;

export function JobsTable({ initialJobs }: { initialJobs: Job[] }) {
  const [jobs, setJobs] = useState(initialJobs);
  const [loaded, setLoaded] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const response = await fetch("/api/jobs", { cache: "no-store" });
        if (!response.ok) return;
        const data = (await response.json()) as Job[];
        if (!cancelled) {
          setJobs(data);
          setLoaded(true);
        }
      } catch {
        // Transient network error; the next poll will retry.
      }
    };
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (!loaded) {
    return <Skeleton className="h-48 w-full" />;
  }

  if (jobs.length === 0) {
    return (
      <Empty>
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <AudioLinesIcon />
          </EmptyMedia>
          <EmptyTitle>No transcriptions yet</EmptyTitle>
          <EmptyDescription>
            Upload an audio file above to start your first job.
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent />
      </Empty>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>File</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Language</TableHead>
          <TableHead>Duration</TableHead>
          <TableHead>Started</TableHead>
          <TableHead className="w-10" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {jobs.map((job) => (
          <TableRow key={job.id}>
            <TableCell>
              <Link href={`/jobs/${job.id}`} className="font-medium hover:underline">
                {job.original_filename}
              </Link>
            </TableCell>
            <TableCell>
              <JobStatusBadge status={job.status} />
            </TableCell>
            <TableCell className="text-muted-foreground">
              {job.transcript?.language ?? job.options.language ?? "auto"}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {formatJobDuration(job.started_at, job.completed_at) ?? "\u2013"}
            </TableCell>
            <TableCell className="text-muted-foreground">
              {formatRelativeTime(job.created_at)}
            </TableCell>
            <TableCell>
              <DeleteJobButton
                jobId={job.id}
                filename={job.original_filename}
                onDeleted={() => setJobs((current) => current.filter((j) => j.id !== job.id))}
              />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
