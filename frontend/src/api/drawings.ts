/** 설계도면 API */

import { del, get, patch, postForm } from "./client";

export interface DrawingItem {
  id: string;
  title: string;
  drawing_no: string;
  equipment: string | null;
  line: string | null;
  description: string | null;
  revision: number;
  status: "PENDING" | "PROCESSING" | "DONE" | "FAILED";
  error: string | null;
  created_at: string;
}

export interface DrawingForm {
  title: string;
  drawing_no: string;
  equipment?: string;
  line?: string;
  description?: string;
}

export const drawingsApi = {
  list: () => get<DrawingItem[]>("/drawings"),
  fileUrl: (id: string) => `/api/v1/drawings/${id}/file`,
  create: (file: File, form: DrawingForm) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("title", form.title);
    fd.append("drawing_no", form.drawing_no);
    if (form.equipment) fd.append("equipment", form.equipment);
    if (form.line) fd.append("line", form.line);
    if (form.description) fd.append("description", form.description);
    return postForm<DrawingItem>("/drawings", fd);
  },
  update: (id: string, body: Partial<DrawingForm>) =>
    patch<DrawingItem>(`/drawings/${id}`, body),
  addRevision: (id: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return postForm<DrawingItem>(`/drawings/${id}/revisions`, fd);
  },
  remove: (id: string) => del(`/drawings/${id}`),
};
