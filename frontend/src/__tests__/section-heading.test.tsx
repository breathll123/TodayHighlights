import { render, screen } from "@testing-library/react";
import { BrainCircuit } from "lucide-react";
import { expect, it } from "vitest";

import { SectionHeading } from "../components/layout/SectionHeading";

it("renders a semantic icon, title, and optional metadata", () => {
  render(<SectionHeading icon={BrainCircuit} title="AI模型排行" meta="10 个模型" />);

  expect(screen.getByRole("heading", { name: "AI模型排行" })).toBeInTheDocument();
  expect(screen.getByTestId("section-heading-icon")).toBeInTheDocument();
  expect(screen.getByText("10 个模型")).toBeInTheDocument();
});

it("renders a concrete block data updated time", () => {
  render(<SectionHeading icon={BrainCircuit} title="AI模型排行" dataUpdatedAt="2026-06-17T13:52:18" />);

  const updatedAt = screen.getByText("更新 13:52");
  const tooltip = screen.getByRole("tooltip");

  expect(updatedAt).toBeInTheDocument();
  expect(updatedAt).toHaveAttribute("aria-describedby", tooltip.id);
  expect(tooltip).toHaveTextContent("数据更新时间");
  expect(tooltip).toHaveTextContent("2026-06-17 13:52:18");
});
