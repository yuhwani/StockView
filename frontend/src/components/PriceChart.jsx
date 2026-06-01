import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const RANGES = [
  { label: "3개월", days: 63 },
  { label: "6개월", days: 126 },
  { label: "1년", days: 252 },
  { label: "전체", days: Infinity },
];

import { useState } from "react";

export default function PriceChart({ candles, region = "KR" }) {
  const [range, setRange] = useState(252);
  if (!candles?.length) return null;

  const sliced =
    range === Infinity ? candles : candles.slice(-range);

  const first = sliced[0].Close;
  const last = sliced[sliced.length - 1].Close;
  const up = last >= first;

  // 색 관습: 한국은 상승=빨강/하락=파랑, 미국은 상승=초록/하락=빨강
  const color = up
    ? region === "US"
      ? "#2f9e44"
      : "#e03131"
    : region === "US"
    ? "#e03131"
    : "#1971c2";

  // 통화 표시
  const fmtPrice = (v) =>
    region === "US"
      ? "$" + v.toLocaleString(undefined, { maximumFractionDigits: 2 })
      : v.toLocaleString() + "원";

  return (
    <div className="card">
      <div className="chart-head">
        <h3>가격 추이</h3>
        <div className="range-tabs">
          {RANGES.map((r) => (
            <button
              key={r.label}
              className={range === r.days ? "active" : ""}
              onClick={() => setRange(r.days)}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={320}>
        <AreaChart data={sliced} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.35} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e5ea" />
          <XAxis
            dataKey="Date"
            tick={{ fill: "#6b7280", fontSize: 11 }}
            minTickGap={40}
          />
          <YAxis
            domain={["auto", "auto"]}
            tick={{ fill: "#6b7280", fontSize: 11 }}
            tickFormatter={(v) => v.toLocaleString()}
            width={64}
          />
          <Tooltip
            contentStyle={{
              background: "#ffffff",
              border: "1px solid #e2e5ea",
              borderRadius: 8,
              color: "#1a1d24",
            }}
            formatter={(v) => [fmtPrice(v), "종가"]}
          />
          <Area
            type="monotone"
            dataKey="Close"
            stroke={color}
            strokeWidth={2}
            fill="url(#g)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
