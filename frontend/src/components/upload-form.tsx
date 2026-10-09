"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { FileUpload } from "@/components/file-upload";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "@/components/ui/toast";
import type { Language } from "@/lib/types";

export function UploadForm() {
  const router = useRouter();
  const [languages, setLanguages] = useState<Language[]>([
    { code: "en", name: "English" },
    { code: "auto", name: "Detect automatically" },
  ]);
  const [language, setLanguage] = useState("en");
  const [file, setFile] = useState<File | null>(null);
  const [speakers, setSpeakers] = useState("");
  const [initialPrompt, setInitialPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetch("/api/languages")
      .then((response) => response.json())
      .then((data: Language[]) => setLanguages(data))
      .catch(() => {
        // Keep the "Detect automatically" fallback; the picker still works.
      });
  }, []);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) {
      toast.add({ title: "Choose an audio file first.", type: "error" });
      return;
    }

    const formData = new FormData();
    formData.set("file", file);
    formData.set("language", language);
    if (speakers.trim()) formData.set("speakers", speakers.trim());
    if (initialPrompt.trim()) formData.set("initial_prompt", initialPrompt.trim());

    setSubmitting(true);
    try {
      const response = await fetch("/api/jobs", { method: "POST", body: formData });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.error ?? "Could not start transcription.");
      }
      toast.add({ title: "Transcription started.", type: "success" });
      router.push(`/jobs/${data.id}`);
      router.refresh();
    } catch (error) {
      toast.add({
        title: "Could not start transcription.",
        description: error instanceof Error ? error.message : undefined,
        type: "error",
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <FieldGroup>
        <Field>
          <FieldLabel htmlFor="audio-file">Audio file</FieldLabel>
          <FileUpload id="audio-file" file={file} onFileChange={setFile} />
        </Field>

        <Field orientation="responsive">
          <Field>
            <FieldLabel htmlFor="language">Language</FieldLabel>
            <Select value={language} onValueChange={(value) => setLanguage(value as string)}>
              <SelectTrigger id="language" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectGroup>
                  {languages.map((item) => (
                    <SelectItem key={item.code} value={item.code}>
                      {item.name}
                    </SelectItem>
                  ))}
                </SelectGroup>
              </SelectContent>
            </Select>
            <FieldDescription>
              Defaults to English; pick &ldquo;Detect automatically&rdquo; for other languages.
            </FieldDescription>
          </Field>

          <Field>
            <FieldLabel htmlFor="speakers">Speaker count</FieldLabel>
            <Input
              id="speakers"
              type="number"
              min={1}
              placeholder="Unknown"
              value={speakers}
              onChange={(event) => setSpeakers(event.target.value)}
            />
            <FieldDescription>Improves diarization when known.</FieldDescription>
          </Field>
        </Field>

        <Field>
          <FieldLabel htmlFor="initial-prompt">Names &amp; vocabulary (optional)</FieldLabel>
          <Textarea
            id="initial-prompt"
            placeholder="Unusual names, acronyms, or specialist terms to prime the model"
            value={initialPrompt}
            onChange={(event) => setInitialPrompt(event.target.value)}
            rows={2}
          />
        </Field>

        <Button type="submit" disabled={submitting}>
          {submitting && <Spinner data-icon="inline-start" />}
          {submitting ? "Starting…" : "Start transcription"}
        </Button>
      </FieldGroup>
    </form>
  );
}
