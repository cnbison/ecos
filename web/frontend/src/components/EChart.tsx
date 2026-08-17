// v0.95.1: 最小 ECharts React 封装 (init/resize/dispose 生命周期, 不引第三方 wrapper)
import { useEffect, useRef } from "react";
import * as echarts from "echarts";

interface EChartProps {
  option: echarts.EChartsOption;
  height?: number;
}

export default function EChart({ option, height = 260 }: EChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = echarts.init(containerRef.current);
    chartRef.current = chart;
    const onResize = () => chart.resize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option, true);
  }, [option]);

  return <div ref={containerRef} style={{ width: "100%", height }} />;
}
