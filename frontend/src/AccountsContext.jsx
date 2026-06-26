import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";

const KEY = "stockview.portfolio";
const WKEY = "stockview.watchlists"; // 계정별 즐겨찾기 { [accId]: [entries] }
const RKEY = "stockview.reportprefs"; // 계정별 보고서 받기 { [accId]: bool }

function load() {
  try {
    const d = JSON.parse(localStorage.getItem(KEY));
    if (d && Array.isArray(d.accounts)) return d;
  } catch {
    /* ignore */
  }
  return { accounts: [], activeId: null, tx: {} };
}

function loadWatch() {
  try {
    return JSON.parse(localStorage.getItem(WKEY)) || {};
  } catch {
    return {};
  }
}

function loadReports() {
  try {
    return JSON.parse(localStorage.getItem(RKEY)) || {};
  } catch {
    return {};
  }
}

const Ctx = createContext(null);

// 로그인 없는 '계좌(프로필)' + 실매매 기록 + 계정별 즐겨찾기를 전역(Context)으로 관리
export function AccountsProvider({ children }) {
  const [state, setState] = useState(load);
  const [watch, setWatch] = useState(loadWatch);
  const [reports, setReports] = useState(loadReports);

  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify(state));
  }, [state]);

  useEffect(() => {
    localStorage.setItem(WKEY, JSON.stringify(watch));
  }, [watch]);

  useEffect(() => {
    localStorage.setItem(RKEY, JSON.stringify(reports));
  }, [reports]);

  // 계정별 보고서 받기 (기본 켜짐)
  const reportOn = useCallback((id) => reports[id] !== false, [reports]);
  const setReportOn = useCallback((id, on) => {
    setReports((r) => ({ ...r, [id]: !!on }));
  }, []);

  // 계정별 즐겨찾기 조회/토글
  const favsOf = useCallback((id) => watch[id] || [], [watch]);
  const toggleFav = useCallback((id, stock) => {
    const entry = {
      Code: stock.Code || stock.code,
      Name: stock.Name || stock.name,
      Region: stock.Region || stock.region || "KR",
      Market: stock.Market || stock.market || "",
    };
    setWatch((w) => {
      const list = w[id] || [];
      const next = list.some((i) => i.Code === entry.Code)
        ? list.filter((i) => i.Code !== entry.Code)
        : [...list, entry];
      return { ...w, [id]: next };
    });
  }, []);

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
    watch,
    favsOf,
    toggleFav,
    reportOn,
    setReportOn,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAccounts() {
  return useContext(Ctx);
}
