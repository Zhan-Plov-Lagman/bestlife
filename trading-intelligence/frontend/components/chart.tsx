"use client";
import { useEffect, useRef } from "react";
import { AreaSeries, ColorType, createChart, type UTCTimestamp } from "lightweight-charts";
export default function Chart({ points }: { points: { time: string; value: number }[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = createChart(ref.current, { autoSize: true, height: 240, layout: { background: { type: ColorType.Solid, color: "#101719" }, textColor: "#7f9494", attributionLogo: true }, grid: { vertLines: { color: "#192326" }, horzLines: { color: "#192326" } }, rightPriceScale: { borderColor: "#233134" }, timeScale: { timeVisible: true, borderColor: "#233134" } });
    const series = chart.addSeries(AreaSeries, { lineColor: "#46d7ab", topColor: "#46d7ab30", bottomColor: "#46d7ab00", lineWidth: 2 });
    const unique = new Map<number, number>();
    for (const p of points.slice(-200)) unique.set(Math.floor(Date.parse(p.time) / 1000), p.value);
    series.setData([...unique].sort((a,b) => a[0]-b[0]).map(([time,value]) => ({ time: time as UTCTimestamp, value })));
    chart.timeScale().fitContent();
    return () => chart.remove();
  }, [points]);
  return <div ref={ref} aria-label="Historical chart" />;
}
