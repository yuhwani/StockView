import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAccounts } from "../useAccounts";
import { computeHoldings } from "../portfolio";
import { getPrices } from "../api";

function money(v, region) {
  if (v == null) return "-";
  const n = Math.round(v);
  return region === "US"
    ? "$" + Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })
    : n.toLocaleString() + "원";
}
function pnlCls(v) {
  return v == null ? "" : v > 0 ? "up" : v < 0 ? "down" : "";
}
function signed(v, region) {
  if (v == null) return "-";
  return (v > 0 ? "+" : "") + money(v, region);
}

export default function PortfolioPage() {
  const acc = useAccounts();
  const navigate = useNavigate();
  const [prices, setPrices] = useState({});

  const txs = acc.activeId ? acc.txOf(acc.activeId) : [];
  const codes = [...new Set(txs.map((t) => t.code))];
  const codesKey = codes.join(",");

  useEffect(() => {
    if (codes.length) {
      getPrices(codes)
        .then((d) => setPrices(d.prices || {}))
        .catch(() => setPrices({}));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [codesKey]);

  if (!acc.active) {
    return (
      <div>
        <Link to="/home" className="back-link">
          ← 홈으로
        </Link>
        <div className="card">
          <p>선택된 계정이 없습니다. 홈에서 계정을 추가/선택하세요.</p>
        </div>
      </div>
    );
  }

  const pf = computeHoldings(txs, prices);
  // 한국·미국 통화가 섞이면 합산 통화 표기가 애매하므로 종목별 통화로 표시,
  // 합계는 원/달러 구분 없이 숫자만(참고용)로 보여준다.

  return (
    <div>
      <Link to="/home" className="back-link">
        ← 홈으로
      </Link>

      <div className="pf-head">
        <h2>📁 {acc.active.name} · 손익</h2>
        <select
          className="ab-select"
          value={acc.activeId}
          onChange={(e) => acc.selectAccount(e.target.value)}
        >
          {acc.accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
      </div>

      {/* 합계 */}
      <div className="pf-summary card">
        <Summary label="총 평가금액" value={money(pf.totalEval, "")} />
        <Summary label="매입원가" value={money(pf.totalCost, "")} />
        <Summary
          label="평가손익"
          value={signed(pf.totalUnrealized, "")}
          cls={pnlCls(pf.totalUnrealized)}
          sub={pf.totalRoi != null ? (pf.totalRoi * 100).toFixed(2) + "%" : null}
        />
        <Summary
          label="실현손익"
          value={signed(pf.totalRealized, "")}
          cls={pnlCls(pf.totalRealized)}
        />
        <Summary
          label="총손익"
          value={signed(pf.totalPnl, "")}
          cls={pnlCls(pf.totalPnl)}
          big
        />
      </div>

      {/* 보유 종목 */}
      {pf.holdings.length === 0 ? (
        <div className="card">
          아직 매매 기록이 없어요. 종목을 검색해 들어가서 매수 기록을 추가해보세요.
        </div>
      ) : (
        <div className="card">
          <h3>보유 종목</h3>
          <div className="pf-table-wrap">
            <table className="pf-table">
              <thead>
                <tr>
                  <th>종목</th>
                  <th className="num">수량</th>
                  <th className="num">평균단가</th>
                  <th className="num">현재가</th>
                  <th className="num">평가손익</th>
                  <th className="num">수익률</th>
                  <th className="num">실현손익</th>
                </tr>
              </thead>
              <tbody>
                {pf.holdings.map((h) => (
                  <tr
                    key={h.code}
                    className="pf-row"
                    onClick={() => navigate(`/stock/${h.code}`)}
                  >
                    <td>
                      <span className="pf-flag">
                        {h.region === "US" ? "🇺🇸" : "🇰🇷"}
                      </span>
                      {h.name}
                      <span className="pf-code">{h.code}</span>
                    </td>
                    <td className="num">{h.qty}</td>
                    <td className="num">{money(h.avg, h.region)}</td>
                    <td className="num">{money(h.current, h.region)}</td>
                    <td className={`num ${pnlCls(h.unrealized)}`}>
                      {h.qty > 0 ? signed(h.unrealized, h.region) : "-"}
                    </td>
                    <td className={`num ${pnlCls(h.roi)}`}>
                      {h.qty > 0 && h.roi != null
                        ? (h.roi > 0 ? "+" : "") + (h.roi * 100).toFixed(2) + "%"
                        : "-"}
                    </td>
                    <td className={`num ${pnlCls(h.realized)}`}>
                      {h.realized ? signed(h.realized, h.region) : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="pf-note">
            직접 입력한 매매 기록 기준입니다. 한국·미국이 섞이면 합계는 통화를 구분하지
            않은 단순 합이라 참고용이에요. 행을 누르면 종목 상세로 이동합니다.
          </p>
        </div>
      )}

      {/* 거래 내역 */}
      {txs.length > 0 && (
        <div className="card">
          <h3>거래 내역</h3>
          <div className="pf-table-wrap">
            <table className="pf-table">
              <thead>
                <tr>
                  <th>날짜</th>
                  <th>종목</th>
                  <th>구분</th>
                  <th className="num">수량</th>
                  <th className="num">가격</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {[...txs].reverse().map((t) => (
                  <tr key={t.id}>
                    <td>{t.date}</td>
                    <td>{t.name}</td>
                    <td className={t.side === "buy" ? "up" : "down"}>
                      {t.side === "buy" ? "매수" : "매도"}
                    </td>
                    <td className="num">{t.qty}</td>
                    <td className="num">{money(t.price, t.region)}</td>
                    <td className="num">
                      <button
                        className="del-tx"
                        onClick={() => acc.removeTrade(acc.activeId, t.id)}
                        title="기록 삭제"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function Summary({ label, value, cls, sub, big }) {
  return (
    <div className={`pf-sum ${big ? "big" : ""}`}>
      <div className="pf-sum-label">{label}</div>
      <div className={`pf-sum-val ${cls || ""}`}>{value}</div>
      {sub && <div className={`pf-sum-sub ${cls || ""}`}>{sub}</div>}
    </div>
  );
}
