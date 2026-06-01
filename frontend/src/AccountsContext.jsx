import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

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

const Ctx = createContext(null);

// 로그인 없는 '계좌(프로필)' + 실매매 기록을 전역(Context)으로 관리
export function AccountsProvider({ children }) {
  const [state, setState] = useState(load);

  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify(state));
  }, [state]);

  const addAccount = useCallback((name) => {
    const id = "acc_" + Date.now();
    setState((s) => ({
      ...s,
      accounts: [...s.accounts, { id, name: (name || "").trim() || "내 계좌" }],
      activeId: id,
      tx: { ...s.tx, [id]: [] },
    }));
    return id;
  }, []);

  const selectAccount = useCallback((id) => {
    setState((s) => ({ ...s, activeId: id }));
  }, []);

  const exitAccount = useCallback(() => {
    setState((s) => ({ ...s, activeId: null }));
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
        activeId: s.activeId === id ? null : s.activeId,
      };
    });
  }, []);

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

  const value = {
    accounts: state.accounts,
    activeId: state.activeId,
    active,
    addAccount,
    selectAccount,
    exitAccount,
    removeAccount,
    addTrade,
    removeTrade,
    txOf,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAccounts() {
  return useContext(Ctx);
}
