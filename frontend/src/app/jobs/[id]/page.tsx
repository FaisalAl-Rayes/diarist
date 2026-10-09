import Link from "next/link";
import { notFound } from "next/navigation";

import { JobDetail } from "@/components/job-detail";
import { BackendError, backendJson } from "@/lib/backend";
import type { Job } from "@/lib/types";
import { ArrowLeftIcon } from "lucide-react";


export default async function JobPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let job: Job;
  try {
    job = await backendJson<Job>(`/api/jobs/${encodeURIComponent(id)}`);
  } catch (error) {
    if (error instanceof BackendError && error.status === 404) {
      notFound();
    }
    throw error;
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-10">
      <Link
        href="/"
        className="flex w-fit items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeftIcon className="size-4" />
        All jobs
      </Link>
      <JobDetail initialJob={job} />
    </main>
  );
}
