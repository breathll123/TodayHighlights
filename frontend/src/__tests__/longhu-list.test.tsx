import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LonghuList } from "../components/layout/LonghuList";
import { FIELD_DEFS } from "../lib/field-defs";

describe("LonghuList", () => {
  it("renders one compact row and exposes the reason through an info tooltip", () => {
    render(
      <LonghuList
        data={[
          {
            id: 1,
            title: "光库科技",
            symbols: ["300620"],
            percent: 19.9979,
            net_amount: 1537055379.98,
            reason: "日涨幅达到15%的前5只证券",
            url: "https://quote.eastmoney.com/300620.html",
          },
        ]}
        fields={FIELD_DEFS.eastmoney_longhu}
      />,
    );

    expect(screen.getByTestId("longhu-list")).toHaveAttribute("data-layout", "compact-list");
    expect(screen.getByText("光库科技")).toBeInTheDocument();
    expect(screen.getByText("300620")).toBeInTheDocument();
    expect(screen.getByText("+20.00%")).toBeInTheDocument();
    expect(screen.getByText("+15.4亿")).toBeInTheDocument();

    const trigger = screen.getByRole("button", { name: "查看光库科技的上榜原因" });
    const tooltip = screen.getByRole("tooltip");
    expect(trigger).toHaveAttribute("aria-describedby", tooltip.id);
    expect(tooltip).toHaveTextContent("日涨幅达到15%的前5只证券");
  });

  it("keeps signed net selling amounts", () => {
    render(
      <LonghuList
        data={[
          {
            id: 2,
            title: "测试净卖出",
            symbols: ["000001"],
            percent: -6.25,
            net_amount: -820000000,
            reason: "日跌幅偏离值达到7%的前5只证券",
          },
        ]}
        fields={FIELD_DEFS.eastmoney_longhu}
      />,
    );

    expect(screen.getByText("-8.2亿")).toBeInTheDocument();
  });
});
