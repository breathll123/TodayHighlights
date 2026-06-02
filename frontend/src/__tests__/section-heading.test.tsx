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
