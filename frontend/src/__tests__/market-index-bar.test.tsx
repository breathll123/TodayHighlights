import { describe, expect, it } from "vitest";
import {
  buildMarketIndexChartData,
  buildPriceDomain,
  getMarketIndexChartLayout,
  MARKET_TIME_TICKS,
  priceToReferencePct,
} from "../components/layout/MarketIndexBar";

describe("MarketIndexBar chart data", () => {
  it("joins the afternoon session directly after the morning session", () => {
    const data = buildMarketIndexChartData(
      [
        { time: "09:30", price: 3000 },
        { time: "11:30", price: 3010 },
        { time: "13:00", price: 3020 },
        { time: "15:00", price: 3030 },
      ],
      3000,
    );

    expect(MARKET_TIME_TICKS).toContain(120);
    expect(data.some((item) => item.time === "午休")).toBe(false);
    expect(data.some((item) => item.time === "11:30" && item.x === 120 && item.price === 3010)).toBe(true);
    expect(data.some((item) => item.time === "13:00" && item.x === 120 && item.price === 3020)).toBe(true);
  });

  it("calculates chart percent changes from the opening reference price", () => {
    const data = buildMarketIndexChartData([{ time: "13:00", price: 3060 }], 3000);

    expect(data[0].pct).toBe(2);
  });

  it("formats the right axis from the same price scale as the opening reference", () => {
    expect(priceToReferencePct(3060, 3000)).toBe(2);
    expect(priceToReferencePct(2940, 3000)).toBe(-2);
  });

  it("includes reported intraday high and low in the chart price domain", () => {
    const data = buildMarketIndexChartData(
      [
        { time: "09:30", price: 3000 },
        { time: "10:00", price: 2995 },
      ],
      3000,
    );

    const [min, max] = buildPriceDomain(data, 3000, 3020, 2980);

    expect(min).toBeLessThan(2980);
    expect(max).toBeGreaterThan(3020);
  });

  it("uses fewer ticks and compact axes on mobile", () => {
    expect(getMarketIndexChartLayout(true)).toEqual({
      ticks: [0, 60, 120, 180, 240],
      axisWidth: 38,
      horizontalMargin: 4,
    });
  });

  it("keeps full time detail while reducing unused desktop margins", () => {
    expect(getMarketIndexChartLayout(false)).toEqual({
      ticks: MARKET_TIME_TICKS,
      axisWidth: 44,
      horizontalMargin: 8,
    });
  });
});
