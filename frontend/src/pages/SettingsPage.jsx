import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getAlertConfig, setAlertConfig } from "../api";

// 알림 설정 (/settings) — 임계값·발굴 옵션을 화면에서 직접 조정
export default function SettingsPage() {
  const [cfg, setCfg] = useState(null);
  const [status, setStatus] = useState("");

  useEffect(() => {
    getAlertConfig()
      .then(setCfg)
      .catch((e) => setStatus("불러오기 실패: " + e.message));
  }, []);

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

  if (!cfg) {
    return (
      <div>
        <Link to="/home" className="back-link">← 홈으로</Link>
        <div className="card">{status || "설정 불러오는 중…"}</div>
      </div>
    );
  }

  return (
    <div className="settings-page">
      <Link to="/home" className="back-link">← 홈으로</Link>

      <div className="card">
        <h3>🔔 알림 설정</h3>
        <p className="set-note">
          텔레그램 실시간 알림의 조건을 직접 조정해요. 저장하면 워커가 다음 점검 때 반영합니다.
        </p>

        <div className="set-group">
          <h4>기본</h4>
          <Field label="알림 방식"
            hint="요약: 정해진 시각에 하루치를 한 통으로 / 실시간: 사건마다 즉시 / 둘 다">
            <select value={cfg.alert_mode}
              onChange={(e) => upd("alert_mode", e.target.value)}>
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
          <Field label="점검 주기 (초)" hint="최소 60초. 짧을수록 빠르지만 호출↑">
            <input type="number" min="60" max="3600" value={cfg.interval_sec}
              onChange={(e) => upd("interval_sec", +e.target.value)} />
          </Field>
          <Field label="관심·보유 급등락 알림 (±%)" hint="이 % 이상 움직이면 알림">
            <input type="number" min="1" max="30" step="0.5" value={cfg.price_move_pct}
              onChange={(e) => upd("price_move_pct", +e.target.value)} />
          </Field>
          <Field label="매수 추천 위주 (노이즈↓)"
            hint="켜면: 급등은 '매수 신호+거래량'일 때만, 급락은 '매도 신호'일 때만 알림. 살/팔 만한 것만.">
            <label className="switch">
              <input type="checkbox" checked={!!cfg.buy_focus}
                onChange={(e) => upd("buy_focus", e.target.checked)} />
              <span>{cfg.buy_focus ? "켜짐" : "꺼짐"}</span>
            </label>
          </Field>
          <Field label="후속 알림 추가변동 (±%)"
            hint="같은 종목은 하루 1회지만, 알림 후 이 % 더 움직이거나 신호가 반전되면 '🔁 후속'으로 한 번 더 (하루 최대 3회)">
            <input type="number" min="2" max="20" step="0.5" value={cfg.followup_move_pct}
              onChange={(e) => upd("followup_move_pct", +e.target.value)} />
          </Field>
        </div>

        <div className="set-group">
          <h4>🔎 발굴 알림 (관심목록 외)</h4>
          <Field label="발굴 알림 켜기" hint="등록 안 한 종목의 급등도 알려줘요">
            <label className="switch">
              <input type="checkbox" checked={!!cfg.discovery_enabled}
                onChange={(e) => upd("discovery_enabled", e.target.checked)} />
              <span>{cfg.discovery_enabled ? "켜짐" : "꺼짐"}</span>
            </label>
          </Field>
          <Field label="발굴 시장" hint="어느 시장에서 발굴할지">
            <select value={cfg.discovery_region}
              onChange={(e) => upd("discovery_region", e.target.value)}>
              <option value="KR">한국</option>
              <option value="US">미국</option>
            </select>
          </Field>
          <Field label="발굴 과열 제외 (+%)" hint="오늘 이미 이만큼 오른 종목은 제외 (추격매수 방지)">
            <input type="number" min="5" max="60" step="1" value={cfg.discovery_max_gain_pct}
              onChange={(e) => upd("discovery_max_gain_pct", +e.target.value)} />
          </Field>
          <Field label="발굴 시작 상승 (+%)" hint="오늘 이 % 이상 오르기 시작 + 강한 매수 신호면 발굴 (낮을수록 일찍)">
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
