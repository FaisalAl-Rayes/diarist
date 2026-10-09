"use client";

import { Trash2Icon } from "lucide-react";
import { useState } from "react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/toast";

export function DeleteJobButton({
  jobId,
  filename,
  onDeleted,
  size = "icon-sm",
  variant = "ghost",
}: {
  jobId: string;
  filename: string;
  onDeleted?: () => void;
  size?: "icon-sm" | "icon" | "sm" | "default";
  variant?: "ghost" | "outline" | "destructive";
}) {
  const [open, setOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    setDeleting(true);
    try {
      const response = await fetch(`/api/jobs/${jobId}`, { method: "DELETE" });
      if (!response.ok && response.status !== 204) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.error ?? "Could not delete the job.");
      }
      toast.add({ title: "Transcription deleted.", type: "success" });
      setOpen(false);
      onDeleted?.();
    } catch (error) {
      toast.add({
        title: "Could not delete the job.",
        description: error instanceof Error ? error.message : undefined,
        type: "error",
      });
    } finally {
      setDeleting(false);
    }
  }

  const isIconOnly = size === "icon-sm" || size === "icon";

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger render={<Button variant={variant} size={size} />}>
        <Trash2Icon data-icon={isIconOnly ? undefined : "inline-start"} />
        {isIconOnly ? <span className="sr-only">Delete {filename}</span> : "Delete"}
      </AlertDialogTrigger>
      <AlertDialogContent size="sm">
        <AlertDialogHeader>
          <AlertDialogTitle>Delete this transcription?</AlertDialogTitle>
          <AlertDialogDescription>
            This permanently deletes &ldquo;{filename}&rdquo; and its transcript. This
            can&apos;t be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel variant="ghost">Cancel</AlertDialogCancel>
          <AlertDialogAction variant="destructive" onClick={handleDelete} disabled={deleting}>
            {deleting ? "Deleting…" : "Delete"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
