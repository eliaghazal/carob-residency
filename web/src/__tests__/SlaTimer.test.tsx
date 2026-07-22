import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { SlaTimer } from "../components/SlaTimer";

afterEach(cleanup);

describe("SlaTimer", () => {
  it("marks a breached SLA", () => {
    render(<SlaTimer dueAt={new Date(Date.now() - 5 * 60_000).toISOString()} answered={false} />);
    expect(screen.getByText(/breached/).className).toContain("sla-breached");
  });

  it("says answered once someone replied", () => {
    render(<SlaTimer dueAt={new Date(Date.now() - 5 * 60_000).toISOString()} answered />);
    expect(screen.getByText("answered")).toBeTruthy();
  });
});
