"use client";

import { FileAudioIcon, UploadIcon, XIcon } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const ACCEPTED_EXTENSIONS = [".m4a", ".mp3", ".wav"];

function formatFileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FileUpload({
  file,
  onFileChange,
  id,
}: {
  file: File | null;
  onFileChange: (file: File | null) => void;
  id?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);

  function handleFiles(fileList: FileList | null) {
    const selected = fileList?.[0];
    if (selected) onFileChange(selected);
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          inputRef.current?.click();
        }
      }}
      onDragOver={(event) => {
        event.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={(event) => {
        event.preventDefault();
        setIsDragging(false);
        handleFiles(event.dataTransfer.files);
      }}
      className={cn(
        "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-4 py-8 text-center transition-colors",
        isDragging ? "border-primary bg-primary/5" : "border-border hover:bg-muted/50",
      )}
    >
      <input
        ref={inputRef}
        id={id}
        type="file"
        accept={ACCEPTED_EXTENSIONS.join(",")}
        className="hidden"
        onChange={(event) => handleFiles(event.target.files)}
      />
      {file ? (
        <div className="flex items-center gap-3">
          <FileAudioIcon className="size-8 text-muted-foreground" />
          <div className="flex flex-col text-left">
            <span className="text-sm font-medium">{file.name}</span>
            <span className="text-xs text-muted-foreground">{formatFileSize(file.size)}</span>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={(event) => {
              event.stopPropagation();
              onFileChange(null);
              if (inputRef.current) inputRef.current.value = "";
            }}
          >
            <XIcon />
            <span className="sr-only">Remove file</span>
          </Button>
        </div>
      ) : (
        <>
          <UploadIcon className="size-8 text-muted-foreground" />
          <div className="flex flex-col gap-1">
            <Button type="button" variant="outline" size="sm" tabIndex={-1}>
              Choose a file
            </Button>
            <span className="text-xs text-muted-foreground">
              or drag and drop &middot; .m4a, .mp3, or .wav
            </span>
          </div>
        </>
      )}
    </div>
  );
}
