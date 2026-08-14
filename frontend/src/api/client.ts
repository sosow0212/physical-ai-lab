/** API 클라이언트 공통 — 에러 봉투({error:{code,message}}) 언래핑 */

export const API_BASE = "/api/v1";

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function unwrap<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let code = "HTTP_ERROR";
    let message = `요청 실패 (${resp.status})`;
    try {
      const body = await resp.json();
      code = body.error?.code ?? code;
      message = body.error?.message ?? message;
    } catch {
      /* 바디 없음 */
    }
    throw new ApiError(code, message, resp.status);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json();
}

export async function get<T>(path: string): Promise<T> {
  return unwrap<T>(await fetch(`${API_BASE}${path}`));
}

export async function del(path: string): Promise<void> {
  await unwrap<void>(await fetch(`${API_BASE}${path}`, { method: "DELETE" }));
}

export async function post<T>(path: string, body?: unknown): Promise<T> {
  return unwrap<T>(
    await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  );
}

export async function postForm<T>(path: string, form: FormData): Promise<T> {
  return unwrap<T>(await fetch(`${API_BASE}${path}`, { method: "POST", body: form }));
}
