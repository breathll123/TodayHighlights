import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { MatchList } from "../components/layout/MatchList";

function match(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    title: "",
    summary: "",
    url: "https://example.com/match/1",
    league: "英超",
    status: 1,
    team_a: "阿森纳",
    team_b: "切尔西",
    score_a: "",
    score_b: "",
    minute: "",
    start_time: "2026-06-01T20:30:00",
    ...overrides,
  };
}

describe("MatchList", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 5, 1, 14, 32, 8));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("groups matches by league and displays each match count", () => {
    render(
      <MatchList
        data={[
          match(),
          match({ id: 2, team_a: "利物浦" }),
          match({ id: 3, league: "西甲", team_a: "皇马" }),
        ]}
      />,
    );

    expect(screen.getByText("英超")).toBeInTheDocument();
    expect(screen.getByText("2 场")).toBeInTheDocument();
    expect(screen.getByText("西甲")).toBeInTheDocument();
    expect(screen.getByText("1 场")).toBeInTheDocument();
  });

  it("refreshes the recent update time when the query timestamp changes with the same data reference", () => {
    const data = [match()];
    const { rerender } = render(<MatchList data={data} dataUpdatedAt={new Date(2026, 5, 1, 14, 32, 8).getTime()} />);

    expect(screen.getByText("最近更新 14:32:08")).toBeInTheDocument();

    rerender(<MatchList data={data} dataUpdatedAt={new Date(2026, 5, 1, 14, 35, 9).getTime()} />);

    expect(screen.getByText("最近更新 14:35:09")).toBeInTheDocument();
  });

  it("shows fixture start time and vs for an unplayed match", () => {
    render(<MatchList data={[match()]} />);

    const row = screen.getByRole("link");
    expect(within(row).getByText("20:30")).toBeInTheDocument();
    expect(within(row).getByText("vs")).toBeInTheDocument();
  });

  it("supports a legacy space-separated fixture start time", () => {
    render(<MatchList data={[match({ start_time: "2026-06-01 20:30:00" })]} />);

    expect(within(screen.getByRole("link")).getByText("20:30")).toBeInTheDocument();
  });

  it("shows a live dot and minute for a second-half live match", () => {
    render(<MatchList data={[match({ status: 8, minute: "67", score_a: "2", score_b: "1" })]} />);

    const row = screen.getByRole("link");
    expect(within(row).getByText("67'")).toBeInTheDocument();
    expect(within(row).getByText("67'").className).toContain("text-red");
    expect(within(row).getByTestId("live-dot")).toBeInTheDocument();
    expect(within(row).getByTestId("live-dot").className).toContain("motion-safe:animate-pulse");
    expect(within(row).getByText("2 - 1")).toBeInTheDocument();
  });

  it("falls back to the half label when a live match has no minute", () => {
    render(<MatchList data={[match({ status: 8, minute: "", score_a: "0", score_b: "0" })]} />);

    expect(within(screen.getByRole("link")).getByText("下半场")).toBeInTheDocument();
  });

  it("falls back to the first-half label when status 2 has no minute", () => {
    render(<MatchList data={[match({ status: 2, minute: "", score_a: "0", score_b: "0" })]} />);

    expect(within(screen.getByRole("link")).getByText("上半场")).toBeInTheDocument();
  });

  it("does not duplicate an existing minute apostrophe", () => {
    render(<MatchList data={[match({ status: 8, minute: "67'", score_a: "2", score_b: "1" })]} />);

    const row = screen.getByRole("link");
    expect(within(row).getByText("67'")).toBeInTheDocument();
    expect(within(row).queryByText("67''")).not.toBeInTheDocument();
  });

  it("shows the final score for a completed match", () => {
    render(<MatchList data={[match({ status: 15, score_a: "3", score_b: "2" })]} />);

    const row = screen.getByRole("link");
    expect(within(row).getByText("完场")).toBeInTheDocument();
    expect(within(row).getByText("3 - 2")).toBeInTheDocument();
  });

  it("uses warm semantic emphasis for postponed and cancelled matches", () => {
    const { rerender } = render(<MatchList data={[match({ status: 18, score_a: "", score_b: "" })]} />);

    expect(within(screen.getByRole("link")).getByText("延期").className).toContain("text-amber");

    rerender(<MatchList data={[match({ status: 19, score_a: "", score_b: "" })]} />);

    expect(within(screen.getByRole("link")).getByText("取消").className).toContain("text-amber");
  });

  it("supports legacy string statuses", () => {
    render(<MatchList data={[match({ status: "Fixture" })]} />);

    const row = screen.getByRole("link");
    expect(within(row).getByText("20:30")).toBeInTheDocument();
    expect(within(row).getByText("vs")).toBeInTheDocument();
  });

  it("supports numeric string statuses", () => {
    const { rerender } = render(<MatchList data={[match({ status: "1" })]} />);

    expect(within(screen.getByRole("link")).getByText("vs")).toBeInTheDocument();

    rerender(<MatchList data={[match({ status: "8", minute: "", score_a: "1", score_b: "0" })]} />);

    expect(within(screen.getByRole("link")).getByText("下半场")).toBeInTheDocument();
  });

  it("uses fallback labels for unknown statuses and missing match details", () => {
    render(
      <MatchList
        data={[match({ status: 99, status_name: "中断", team_a: "", team_b: "", score_a: "", score_b: "" })]}
      />,
    );

    const row = screen.getByRole("link");
    expect(within(row).getByText("中断")).toBeInTheDocument();
    expect(within(row).getAllByText("待定")).toHaveLength(2);
    expect(within(row).getByText("-")).toBeInTheDocument();
  });

  it("renders matches without a URL as non-clickable rows", () => {
    render(<MatchList data={[match({ url: undefined })]} />);

    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByTestId("match-row")).not.toHaveAttribute("href");
    expect(screen.queryByTestId("linked-row-affordance")).not.toBeInTheDocument();
  });

  it("opens matches with a URL in a new tab", () => {
    render(<MatchList data={[match()]} />);

    expect(screen.getByRole("link")).toHaveAttribute("href", "https://example.com/match/1");
    expect(screen.getByRole("link")).toHaveAttribute("target", "_blank");
    expect(screen.getByRole("link")).toHaveAttribute("rel", "noopener noreferrer");
    expect(within(screen.getByRole("link")).getByTestId("linked-row-affordance")).toBeInTheDocument();
  });
});
