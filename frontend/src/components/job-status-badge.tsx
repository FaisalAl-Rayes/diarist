import { CheckIcon, CircleDashedIcon, Loader2Icon, XIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { JobStatus } from "@/lib/types";

const STATUS_CONFIG: Record<
  JobStatus,
  { label: string; variant: "secondary" | "default" | "destructive" | "outline"; Icon: typeof CheckIcon }
> = {
  queued: { label: "Queued", variant: "outline", Icon: CircleDashedIcon },
  processing: { label: "Processing", variant: "secondary", Icon: Loader2Icon },
  completed: { label: "Completed", variant: "default", Icon: CheckIcon },
  failed: { label: "Failed", variant: "destructive", Icon: XIcon },
};

export function JobStatusBadge({ status }: { status: JobStatus }) {
  const { label, variant, Icon } = STATUS_CONFIG[status];
  return (
    <Badge variant={variant}>
      <Icon data-icon="inline-start" className={status === "processing" ? "animate-spin" : ""} />
      {label}
    </Badge>
  );
}
