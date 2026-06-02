// 거래 내역 + 현재가로 보유 종목과 손익을 계산 (평균매입가 방식)

// 특정 종목의 현재 보유 수량 (매도는 보유분까지만, 음수 불가)
export function heldQtyOf(txs, code) {
  let qty = 0;
  const sorted = [...txs]
    .filter((t) => t.code === code)
    .sort((a, b) => (a.date < b.date ? -1 : 1));
  for (const t of sorted) {
    const q = Number(t.qty) || 0;
    if (t.side === "buy") qty += q;
    else qty -= Math.min(q, qty); // 보유보다 많이 못 팜
  }
  return qty;
}

export function computeHoldings(txs, prices) {
  // 종목별로 거래를 시간순 처리
  const byCode = {};
  const sorted = [...txs].sort((a, b) => (a.date < b.date ? -1 : 1));

  for (const t of sorted) {
    const h = (byCode[t.code] = byCode[t.code] || {
      code: t.code,
      name: t.name,
      region: t.region,
      qty: 0,
      cost: 0, // 보유분 총 매입원가
      realized: 0, // 실현손익
      invested: 0, // 누적 매수금액
    });
    const qty = Number(t.qty) || 0;
    const price = Number(t.price) || 0;
    if (t.side === "buy") {
      h.qty += qty;
      h.cost += qty * price;
      h.invested += qty * price;
    } else {
      // 매도: 평균단가 기준 실현손익
      const avg = h.qty > 0 ? h.cost / h.qty : 0;
      const sellQty = Math.min(qty, h.qty);
      h.realized += (price - avg) * sellQty;
      h.cost -= avg * sellQty;
      h.qty -= sellQty;
    }
  }

  const holdings = [];
  let totalEval = 0,
    totalCost = 0,
    totalRealized = 0;

  for (const code in byCode) {
    const h = byCode[code];
    const cur = prices?.[code]?.price ?? null;
    const avg = h.qty > 0 ? h.cost / h.qty : 0;
    const evalValue = cur != null ? cur * h.qty : null;
    const unrealized = evalValue != null ? evalValue - h.cost : null;
    const roi = h.cost > 0 && unrealized != null ? unrealized / h.cost : null;

    totalRealized += h.realized;
    if (h.qty > 0 && evalValue != null) {
      totalEval += evalValue;
      totalCost += h.cost;
    }

    holdings.push({
      code: h.code,
      name: h.name,
      region: h.region,
      qty: h.qty,
      avg,
      current: cur,
      evalValue,
      unrealized,
      roi,
      realized: h.realized,
    });
  }

  // 전량 매도(0주)한 종목은 보유 목록에서 제외 (실현손익은 합계에 이미 반영됨)
  const visible = holdings
    .filter((h) => h.qty > 0)
    .sort((a, b) => (b.evalValue || 0) - (a.evalValue || 0));

  const totalUnrealized = totalEval - totalCost;
  return {
    holdings: visible,
    totalEval,
    totalCost,
    totalUnrealized,
    totalRealized,
    totalPnl: totalUnrealized + totalRealized,
    totalRoi: totalCost > 0 ? totalUnrealized / totalCost : null,
  };
}
