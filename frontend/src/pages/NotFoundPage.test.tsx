// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { NotFoundPage } from "./NotFoundPage";

const mockNavigate = vi.fn();

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => mockNavigate };
});

const renderPage = () =>
  render(
    <MemoryRouter>
      <NotFoundPage />
    </MemoryRouter>,
  );

describe("NotFoundPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders 404 heading and page-not-found text", () => {
    renderPage();
    expect(screen.getByText("404")).toBeTruthy();
    expect(screen.getByText(/page not found/i)).toBeTruthy();
  });

  it("calls navigate(-1) when Go Back is clicked", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /go back/i }));
    expect(mockNavigate).toHaveBeenCalledWith(-1);
  });

  it("navigates to / when Home Page is clicked", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /home page/i }));
    expect(mockNavigate).toHaveBeenCalledWith("/");
  });
});
