import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { InternalAxiosRequestConfig } from "axios";

const getStateMock = vi.hoisted(() => vi.fn());
const dispatchMock = vi.hoisted(() => vi.fn());

vi.mock("../app/store", () => ({
  store: {
    getState: getStateMock,
    dispatch: dispatchMock,
  },
}));

vi.mock("@/store/authSlice", () => ({
  logout: vi.fn(() => ({ type: "auth/logout" })),
  refreshToken: vi.fn(() => ({ type: "auth/refresh" })),
}));

vi.mock("@/store/errorSlice", () => ({
  setError: vi.fn((payload: unknown) => ({ type: "error/set", payload })),
}));

import api from "./api";

const getRequestInterceptor = () =>
  (api.interceptors.request as unknown as {
    handlers: Array<{
      fulfilled: (config: InternalAxiosRequestConfig) => InternalAxiosRequestConfig;
    }>;
  }).handlers[0].fulfilled;

describe("api request interceptor", () => {
  beforeEach(() => {
    getStateMock.mockReturnValue({
      auth: {
        tokens: null,
        activeOrganization: null,
      },
    });
    dispatchMock.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("injects bearer token and active organization header from store context", () => {
    getStateMock.mockReturnValue({
      auth: {
        tokens: { access: "token-123" },
        activeOrganization: { id: "org-123" },
      },
    });

    const interceptor = getRequestInterceptor();
    const config = interceptor({
      headers: {},
    } as unknown as InternalAxiosRequestConfig);

    expect(config.headers.Authorization).toBe("Bearer token-123");
    expect(config.headers["X-Active-Organization-ID"]).toBe("org-123");
  });

  it("preserves an explicit organization header instead of overwriting it from store context", () => {
    getStateMock.mockReturnValue({
      auth: {
        tokens: { access: "token-123" },
        activeOrganization: { id: "org-from-store" },
      },
    });

    const interceptor = getRequestInterceptor();
    const config = interceptor({
      headers: {
        "X-Active-Organization-ID": "org-explicit",
      },
    } as unknown as InternalAxiosRequestConfig);

    expect(config.headers.Authorization).toBe("Bearer token-123");
    expect(config.headers["X-Active-Organization-ID"]).toBe("org-explicit");
  });

  it("removes stale organization headers when no active organization context is available", () => {
    getStateMock.mockReturnValue({
      auth: {
        tokens: null,
        activeOrganization: null,
      },
    });

    const interceptor = getRequestInterceptor();
    const config = interceptor({
      headers: {
        "X-Active-Organization-ID": "",
      },
    } as unknown as InternalAxiosRequestConfig);

    expect(config.headers.Authorization).toBeUndefined();
    expect(config.headers["X-Active-Organization-ID"]).toBeUndefined();
  });
});
