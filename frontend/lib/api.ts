const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        ...(init?.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
        ...init?.headers,
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.");
  }

  if (!res.ok) {
    let detail = "Ocorreu um erro inesperado.";
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // resposta sem corpo JSON — mantém a mensagem genérica
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  postForm: <T>(path: string, form: FormData) =>
    request<T>(path, { method: "POST", body: form }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
};

export { API_URL };
