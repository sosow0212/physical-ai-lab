/** 매뉴얼 문서 API */

import { del, get, post, postForm } from "./client";

export interface DocumentItem {
  id: string;
  title: string;
  status: "PENDING" | "PROCESSING" | "DONE" | "FAILED";
  size_bytes: number;
  page_count: number | null;
  chunk_count: number | null;
  equipment_refs: string[];
  error: string | null;
  created_at: string;
}

export interface JobItem {
  id: string;
  document_id: string;
  type: string;
  action: string;
  status: "PENDING" | "RUNNING" | "DONE" | "FAILED" | "DEAD";
  attempts: number;
  last_error: string | null;
  created_at: string;
}

interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export const documentsApi = {
  list: () => get<Page<DocumentItem>>("/documents"),
  upload: (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return postForm<{ documents: DocumentItem[] }>("/documents", form);
  },
  remove: (id: string) => del(`/documents/${id}`),
  reingest: (id: string) => post<DocumentItem>(`/documents/${id}/reingest`),
  jobs: () => get<Page<JobItem>>("/pipeline/jobs"),
};
