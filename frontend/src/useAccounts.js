import { useCallback, useEffect, useState } from "react";

const KEY = "stockview.portfolio";

function load() {
  try {
    const d = JSON.parse(localStorage.getItem(KEY));
    if (d && Array.isArray(d.accounts)) return d;
  } catch {
    /* ignore */
  }
  return { accounts: [], activeId: null, tx: {} };
}

// 로그인 없는 '계좌(프로필)' + 모의 매매 기록을 localStorage로 관리
export function useAccounts() {
  const [state, setState] = useState(load);

  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify(state));
  }, [state]);

  const addAccount = useCallback((name) => {
    const id = "acc_" + Date.now();
    setState((s) => ({
      ...s,
      accounts: [...s.accounts, { id, name: name.trim() || "내 계좌" }],
      activeId: id,
      tx: { ...s.tx, [id]: [] },
    }));
    return id;
  }, []);

  const selectAccount = useCallback((id) => {
    setState((s) => ({ ...s, activeId: id }));
  }, []);

  const removeAccount = useCallback((id) => {
    setState((s) => {
      const tx = { ...s.tx };
      delete tx[id];
      const accounts = s.accounts.filter((a) => a.id !== id);
      return {
        ...s,
        accounts,
        tx,
        activeId: s.activeId === id ? (accounts[0]?.id ?? null) : s.activeId,
      };
    });
  }, []);

  // 매수/매도 기록 추가
  const addTrade = useCallback((accountId, trade) => {
    setState((s) => ({
      ...s,
      tx: {
        ...s.tx,
        [accountId]: [
          ...(s.tx[accountId] || []),
          { id: "tx_" + Date.now(), ...trade },
        ],
      },
    }));
  }, []);

  const removeTrade = useCallback((accountId, txId) => {
    setState((s) => ({
      ...s,
      tx: {
        ...s.tx,
        [accountId]: (s.tx[accountId] || []).filter((t) => t.id !== txId),
      },
    }));
  }, []);

  const active = state.accounts.find((a) => a.id === state.activeId) || null;
  const txOf = (id) => state.tx[id] || [];

  return {
    accounts: state.accounts,
    activeId: state.activeId,
    active,
    addAccount,
    selectAccount,
    removeAccount,
    addTrade,
    removeTrade,
    txOf,
  };
}
