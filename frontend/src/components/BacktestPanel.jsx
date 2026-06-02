import {
  Line,
  LineChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from "recharts";

function pct(v) {
  return v == null ? "-" : (v > 0 ? "+" : "") + (v * 100).toFixed(1) + "%";
}

export default function BacktestPanel({ backtest, loading }) {
  return (
    <div className="card bt-card">
      <h3>🧪 수익률 백테스트</h3>
      <p className="bt-caveat">
        ML 방향예측대로 <b>‘상승 예측일만 보유(아니면 현금)’</b> 했을 때 vs 단순 보유.
        앞 80%로 학습 → 뒤 20% 구간 검증 (수수료·세금 미반영, 참고용).
      </p>

      {loading ? (
        <div className="bt-loading">백테스트 계산 중… (모델 학습에 몇 초)</div>
      ) : !backtest?.curve?.length ? (
        <div className="bt-loading">백테스트할 데이터가 부족합니다.</div>
      ) : (
        <>
          <div className="bt-metrics">
            <Metric
              label="전략 수익률"
              value={pct(backtest.strategy_return)}
              cls={backtest.strategy_return > 0 ? "up" : "down"}
            />
            <Metric
              label="단순보유"
              value={pct(backtest.buyhold_return)}
              cls={backtest.buyhold_return > 0 ? "up" : "down"}
            />
            <Metric label="적중률" value={(backtest.hit_rate * 100).toFixed(0) + "%"} />
            <Metric
              label="전략 MDD"
              value={pct(backtest.strategy_mdd)}
              cls="down"
              hint="최대낙폭"
            />
            <Metric
              label="보유 MDD"
              value={pct(backtest.buyhold_mdd)}
              cls="down"
              hint="최대낙폭"
            />
          </div>

          <ResponsiveContainer width="100%" height={260}>
            <LineChart
              data={backtest.curve}
              margin={{ top: 8, right: 10, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e5ea" />
              <XAxis
                dataKey="date"
                tick={{ fill: "#6b7280", fontSize: 11 }}
                minTickGap={50}
              />
              <YAxis
                tick={{ fill: "#6b7280", fontSize: 11 }}
                tickFormatter={(v) => (v * 100).toFixed(0) + "%"}
                width={48}
              />
              <Tooltip
                contentStyle={{
                  background: "#fff",
                  border: "1px solid #e2e5ea",
                  borderRadius: 8,
                }}
                formatter={(v, name) => [
                  (v > 0 ? "+" : "") + (v * 100).toFixed(1) + "%",
                  name,
                ]}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="strategy"
                name="전략(ML)"
                stroke="#4263eb"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="hold"
                name="단순보유"
                stroke="#9aa3b5"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>

          <p className="bt-period">
            검증 구간: {backtest.period_start} ~ {backtest.period_end} (
            {backtest.days}거래일, 보유 {backtest.long_days}일)
          </p>
        </>
      )}
    </div>
  );
}

function Metric({ label, value, cls, hint }) {
  return (
    <div className="bt-metric">
      <div className="bt-m-label">{label}</div>
      <div className={`bt-m-val ${cls || ""}`}>{value}</div>
      {hint && <div className="bt-m-hint">{hint}</div>}
    </div>
  );
}
