// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("@/components/passwords/ChangePasswordForm", () => ({
  ChangePasswordForm: () => (
    <div data-testid="change-password-form">ChangePasswordForm</div>
  ),
}));

vi.mock("@/components/passwords/ResetPasswordForm", () => ({
  ResetPasswordForm: () => (
    <div data-testid="reset-password-form">ResetPasswordForm</div>
  ),
}));

vi.mock("@/components/rubrics/RubricBuilder", () => ({
  RubricBuilder: () => <div data-testid="rubric-builder">RubricBuilder</div>,
}));

const { default: ChangePasswordPage } = await import("./ChangePasswordPage");
const { default: ResetPasswordPage } = await import("./ResetPasswordPage");
const { default: RubricBuilderPage } = await import("./RubricBuilderPage");

describe("Thin-wrapper pages render their child components", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("ChangePasswordPage renders ChangePasswordForm", () => {
    render(
      <MemoryRouter>
        <ChangePasswordPage />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("change-password-form")).toBeTruthy();
  });

  it("ResetPasswordPage renders ResetPasswordForm", () => {
    render(
      <MemoryRouter>
        <ResetPasswordPage />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("reset-password-form")).toBeTruthy();
  });

  it("RubricBuilderPage renders RubricBuilder inside a container", () => {
    render(
      <MemoryRouter>
        <RubricBuilderPage />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("rubric-builder")).toBeTruthy();
  });
});
