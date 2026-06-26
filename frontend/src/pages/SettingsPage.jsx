import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAlertConfig, setAlertConfig } from "../api";
import { useAccounts } from "../AccountsContext";

// 알림 설정 (/settings)
//  - 계정별: '내 보고서 받기' (모든 계정에서 선택)
//  - 전역(발굴·요약정리 등): 관리자(yuhwani) 계정에서만 관리
export default function SettingsPage() {
  const { active, accounts, reportOn, setReportOn } = useAccounts();
  const [cfg, setCfg] = useState(null);
  const [status, setStatus] = useState("");

  // 관리자 = 'yuhwani' 계정 (없으면 첫 계정)
  const admin = accounts.find((a) => a.name === "yuhwani") || accounts[0];
  const isAdmin = active && admin && active.id === admin.id;

  useEffect(() => {
    if (!isAdmin) return; // 전역 설정은 관리자만 로드
    getAlertConfig()
      .then(setCfg)
      .catch((e) => setStatus("불러오기 실패: " + e.message));
  }, [isAdmin]);

  const upd = (k, v) => setCfg((c) => ({ ...c, [k]: v }));

  const save = () => {
    setStatus("저장 중…");
    setAlertConfig(cfg)
      .then((saved) => {
        setCfg(saved);
        setStatus("✅ 저장됐어요. 워커가 다음 점검 주기에 반영합니다.");
      })
      .catch((e) => setStatus("저장 실패: " + e.message));
  };

  const myReport = active ? reportOn(active.id) : false;

  return (
    <div className="settings-page">
      <Link to="/home" className="back-link">← 홈으로</Link>

      {/* 계정별 — 모든 계정에서 선택 */}
      <div className="card">
        <h3>📁 {active?.name || "내 계좌"} — 내 알림</h3>
        <p className="set-note">
          이 계정의 보고서를 받을지 선택해요. (보고서 = 요약 시각에 오는 내 보유·관심 종목 현황)
        </p>
        <div className="set-group">
          <Field label="내 보고서 받기"
            hint="켜면: 요약 시각(12·18시 등)에 이 계정의 '보유·관심 종목 보고서'를 텔레그램으로 받아요">
            <label className="switch">
              <input type="checkbox" checked={myReport}
                onChange={(e) => active && setReportOn(active.id, e.target.checked)} />
              <span>{myReport ? "받기" : "안 받기"}</span>
            </label>
          </Field>
        </div>
      </div>

      {/* 전역 — 관리자(yuhwani)만 */}
      {!isAdmin ? (
        <div className="card">
          <p className="set-note">
            🔒 <b>발굴 알림</b>과 <b>12·18시 요약정리</b> 등 전체 알림은
            관리자(<b>{admin?.name || "yuhwani"}</b>) 계정에서 관리해요.
            이 계정에선 위의 <b>내 보고서 받기</b>만 설정할 수 있어요.
          </p>
        </div>
      ) : !cfg ? (
        <div className="card">{status || "전역 설정 불러오는 중…"}</div>
      ) : (
        <div className="card">
          <h3>🔔 전체 알림 설정 <small style={{ color: "var(--muted)", fontWeight: 500 }}>· 관리자</small></h3>
          <p className="set-note">
            발굴·요약정리 등 전체 텔레그램 알림 조건이에요. 저장하면 워커가 다음 점검 때 반영합니다.
          </p>

          <div className="set-group">
            <h4>기본</h4>
            <Field label="알림 방식"
              hint="요약: 정해진 시각에 하루치를 한 통으로 / 실시간: 사건마다 즉시 / 둘 다">
              <select value={cfg.alert_mode} onChange={(e) => upd("alert_mode", e.target.value)}>
                <option value="digest">요약 (정해진 시각)</option>
                <option value="realtime">실시간</option>
                <option value="both">둘 다</option>
              </select>
            </Field>
            {cfg.alert_mode !== "realtime" && (
              <Field label="요약 발송 시각" hint="시(0~23), 콤마로 구분. 예: 12,18 (점심·퇴근)">
                <input type="text" value={cfg.digest_hours}
                  onChange={(e) => upd("digest_hours", e.target.value)} />
              </Field>
            )}
            <Field label="계정별 보고서 (전체 스위치)"
              hint="끄면 모든 계정 보고서를 안 보냄. 켠 상태에서 계정마다 '내 보고서 받기'로 개별 선택">
              <label className="switch">
                <input type="checkbox" checked={!!cfg.account_reports}
                  onChange={(e) => upd("account_reports", e.target.checked)} />
                <span>{cfg.account_reports ? "켜짐" : "꺼짐"}</span>
              </label>
            </Field>
            <Field label="점검 주기 (초)" hint="최소 60초. 짧을수록 빠르지만 호출↑">
              <input type="number" min="60" max="3600" value={cfg.interval_sec}
                onChange={(e) => upd("interval_sec", +e.target.value)} />
            </Field>
            <Field label="관심·보유 급등락 알림 (±%)" hint="이 % 이상 움직이면 알림">
              <input type="number" min="1" max="30" step="0.5" value={cfg.price_move_pct}
                onChange={(e) => upd("price_move_pct", +e.target.value)} />
            </Field>
            <Field label="매수 추천 위주 (노이즈↓)"
              hint="켜면: 급등은 '매수 신호+거래량'일 때만, 급락은 '매도 신호'일 때만 알림.">
              <label className="switch">
                <input type="checkbox" checked={!!cfg.buy_focus}
                  onChange={(e) => upd("buy_focus", e.target.checked)} />
                <span>{cfg.buy_focus ? "켜짐" : "꺼짐"}</span>
              </label>
            </Field>
            <Field label="후속 알림 추가변동 (±%)"
              hint="같은 종목은 하루 1회지만, 알림 후 이 % 더 움직이거나 신호 반전 시 '🔁 후속' (하루 3회)">
              <input type="number" min="2" max="20" step="0.5" value={cfg.followup_move_pct}
                onChange={(e) => upd("followup_move_pct", +e.target.value)} />
            </Field>
          </div>

          <div className="set-group">
            <h4>🔎 발굴 알림 (관심목록 외)</h4>
            <Field label="발굴 알림 켜기" hint="등록 안 한 종목의 강한 매수 신호도 발굴">
              <label className="switch">
                <input type="checkbox" checked={!!cfg.discovery_enabled}
                  onChange={(e) => upd("discovery_enabled", e.target.checked)} />
                <span>{cfg.discovery_enabled ? "켜짐" : "꺼짐"}</span>
              </label>
            </Field>
            <Field label="발굴은 실시간으로" hint="켜면: 요약 모드여도 발굴은 즉시 발송">
              <label className="switch">
                <input type="checkbox" checked={!!cfg.discovery_realtime}
                  onChange={(e) => upd("discovery_realtime", e.target.checked)} />
                <span>{cfg.discovery_realtime ? "실시간" : "요약 따름"}</span>
              </label>
            </Field>
            <Field label="발굴 시장" hint="어느 시장에서 발굴할지">
              <select value={cfg.discovery_region} onChange={(e) => upd("discovery_region", e.target.value)}>
                <option value="KR">한국</option>
                <option value="US">미국</option>
              </select>
            </Field>
            <Field label="발굴 과열 제외 (+%)" hint="오늘 이미 이만큼 오른 종목은 제외 (추격 방지)">
              <input type="number" min="5" max="60" step="1" value={cfg.discovery_max_gain_pct}
                onChange={(e) => upd("discovery_max_gain_pct", +e.target.value)} />
            </Field>
            <Field label="발굴 시작 상승 (+%)" hint="오늘 이 % 이상 오르기 시작 + 강한 매수 신호면 발굴">
              <input type="number" min="3" max="30" step="0.5" value={cfg.discovery_move_pct}
                onChange={(e) => upd("discovery_move_pct", +e.target.value)} />
            </Field>
            <Field label="발굴 최소 시총 (억원)" hint="이 미만 잡주는 제외">
              <input type="number" min="100" max="1000000" step="100" value={cfg.discovery_min_marcap_eok}
                onChange={(e) => upd("discovery_min_marcap_eok", +e.target.value)} />
            </Field>
            <Field label="한 번에 최대 발굴 수" hint="한 점검당 발굴 알림 개수 제한">
              <input type="number" min="1" max="10" value={cfg.discovery_max_per_cycle}
                onChange={(e) => upd("discovery_max_per_cycle", +e.target.value)} />
            </Field>
          </div>

          <div className="set-actions">
            <button className="primary-btn" onClick={save}>저장</button>
            {status && <span className="set-status">{status}</span>}
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <div className="set-field">
      <div className="set-label">
        <span>{label}</span>
        {hint && <small>{hint}</small>}
      </div>
      <div className="set-input">{children}</div>
    </div>
  );
}
