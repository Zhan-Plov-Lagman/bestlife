import { expect, test } from "vitest";
import { money } from "../lib/api";
test("missing metrics are not fabricated zeroes", () => {
  expect(money(null)).toBe("—");
  expect(money("0")).toBe("$0.00");
  expect(money("-1.25")).toBe("-$1.25");
});
