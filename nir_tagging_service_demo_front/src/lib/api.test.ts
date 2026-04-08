import { describe, expect, it } from "vitest";

import { buildReadinessUrl, resolveApiBaseUrl } from "./api";

describe("api url helpers", () => {
  it("rewrites local backend absolute url to vite proxy path in dev", () => {
    expect(
      resolveApiBaseUrl("http://127.0.0.1:8000/api/v1/tagging", "http://localhost:5173"),
    ).toBe("/api/v1/tagging");
  });

  it("keeps absolute api url outside vite dev origin", () => {
    expect(
      resolveApiBaseUrl("http://127.0.0.1:8000/api/v1/tagging", "http://localhost:3000"),
    ).toBe("http://127.0.0.1:8000/api/v1/tagging");
  });

  it("builds readiness url from proxied base", () => {
    expect(
      buildReadinessUrl("http://127.0.0.1:8000/api/v1/tagging", "http://localhost:5173"),
    ).toBe("/readiness");
  });
});
