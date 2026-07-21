import { getDataProvider } from "./data-provider/provider";
export { apiUrl } from "./data-provider/api-provider";

export async function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  return getDataProvider().get<T>(path, signal);
}

export async function patchJson<T>(path: string, body: unknown): Promise<T> {
  return getDataProvider().patch<T>(path, body);
}
