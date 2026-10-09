import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { JobsTable } from "@/components/jobs-table";
import { ModeToggle } from "@/components/mode-toggle";
import { UploadForm } from "@/components/upload-form";
import { backendJson } from "@/lib/backend";
import type { Job } from "@/lib/types";


export default async function HomePage() {
  const jobs = await backendJson<Job[]>("/api/jobs").catch(() => [] as Job[]);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-8 px-4 py-10">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element -- tiny static SVG mark, no benefit from next/image */}
          <img src="/logo.svg" alt="" className="size-9 shrink-0" />
          <div>
            <h1 className="text-xl font-medium">Diarist</h1>
            <p className="text-sm text-muted-foreground">
              Upload a recording to get a word-timestamped, speaker-labeled transcript.
            </p>
          </div>
        </div>
        <ModeToggle />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>New transcription</CardTitle>
        </CardHeader>
        <CardContent>
          <UploadForm />
        </CardContent>
      </Card>

      <div className="flex flex-col gap-3">
        <h2 className="text-sm font-medium text-muted-foreground">Jobs</h2>
        <JobsTable initialJobs={jobs} />
      </div>
    </main>
  );
}
