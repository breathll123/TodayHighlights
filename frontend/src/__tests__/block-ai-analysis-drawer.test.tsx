import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it, vi } from "vitest";

import { BlockAIAnalysisDrawer } from "../components/layout/BlockAIAnalysisDrawer";

it("closes when the outside backdrop is clicked", () => {
  const onClose = vi.fn();

  render(
    <MemoryRouter>
      <BlockAIAnalysisDrawer
        open
        title="当日比赛"
        analysis={null}
        isLoading={false}
        error={null}
        requiresLogin={false}
        onClose={onClose}
      />
    </MemoryRouter>
  );

  expect(screen.getByLabelText("AI 分析")).toBeInTheDocument();

  fireEvent.click(screen.getByTestId("ai-analysis-backdrop"));

  expect(onClose).toHaveBeenCalledTimes(1);
});
