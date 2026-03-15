export async function readJsonResponse(response) {
  const raw = await response.text();
  if (!raw) {
    return null;
  }

  try {
    return JSON.parse(raw);
  } catch {
    if (!response.ok) {
      throw new Error(raw.trim() || `Request failed with ${response.status}`);
    }
    throw new Error("Received an unreadable server response.");
  }
}

export async function apiRequest(path, { method = "GET", token = null, body = null } = {}) {
  const response = await fetch(path, {
    method,
    credentials: "include",
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  const payload = await readJsonResponse(response);
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.message || `Request failed with ${response.status}`);
  }
  return payload;
}
