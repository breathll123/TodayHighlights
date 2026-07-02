// -*- coding: utf-8 -*-
import { describe, it, expect } from "vitest";
import football from "../assets/lottie/football.json";
import robot from "../assets/lottie/robot.json";
import gamepad from "../assets/lottie/gamepad.json";
import kline from "../assets/lottie/kline.json";
import radar from "../assets/lottie/radar.json";
import generic from "../assets/lottie/generic.json";

const ASSETS: Record<string, any> = { football, robot, gamepad, kline, radar, generic };

describe("lottie assets", () => {
  for (const [name, data] of Object.entries(ASSETS)) {
    it(`${name}.json 是合法的 Lottie 文档`, () => {
      expect(data.v).toBe("5.7.4");
      expect(data.fr).toBe(60);
      expect(data.op).toBe(120);
      expect(data.w).toBe(240);
      expect(data.h).toBe(240);
      expect(Array.isArray(data.layers)).toBe(true);
      expect(data.layers.length).toBeGreaterThan(0);
      for (const layer of data.layers) {
        expect(layer.ty).toBe(4); // 全部是 shape layer
        expect(Array.isArray(layer.shapes)).toBe(true);
      }
    });
  }
});
