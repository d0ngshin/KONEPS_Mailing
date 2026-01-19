import os
import requests
import pandas as pd
from datetime import datetime, timedelta, date
import holidayskr
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==================================================
# 1. 환경변수 (GitHub Secrets)
# ==================================================

SERVICE_KEY = os.environ["SERVICE_KEY"]      # 공공데이터포털 인증키
GMAIL_USER = os.environ["GMAIL_USER"]        # 내 Gmail
GMAIL_APP_PW = os.environ["GMAIL_APP_PW"]    # Gmail 앱 비밀번호
MAIL_TO = os.environ["MAIL_TO"]              # 회사 메일

# ==================================================
# 2. 기본 설정
# ==================================================

BASE_URL = (
    "https://apis.data.go.kr/1230000/ad/"
    "BidPublicInfoService/getBidPblancListInfoThng"
)

AGENCIES = ["서울시청", "경찰청", "한강유역환경청"]
KEYWORDS = ["복합기", "사무기기", "프린터", "출력"]

DAYS = 5
ROWS_PER_PAGE = 100

# ==================================================
# 3. 주말 / 한국 공휴일 체크 (holidayskr)
# ==================================================

today = date.today()
kr_holidays = holidayskr.Holidays()

if today.weekday() >= 5 or today in kr_holidays:
    print("🚫 주말 또는 한국 공휴일 → 실행 종료")
    exit(0)

# ==================================================
# 4. 최근 N일 공고 전체 조회 (페이지 순회)
# ==================================================

def fetch_recent_bids(days=DAYS):
    now = datetime.now()
    start_day = now - timedelta(days=days)

    all_rows = []
    page = 1

    while True:
        params = {
            "serviceKey": SERVICE_KEY,
            "pageNo": page,
            "numOfRows": ROWS_PER_PAGE,
            "type": "json",
            "inqryDiv": "1",
            "inqryBgnDt": start_day.strftime("%Y%m%d0000"),
            "inqryEndDt": now.strftime("%Y%m%d2359"),
        }

        res = requests.get(BASE_URL, params=params, timeout=10)
        res.raise_for_status()

        items = res.json().get("response", {}) \
                         .get("body", {}) \
                         .get("items", [])

        if not items:
            break

        for item in items:
            all_rows.append({
                "공고번호": item.get("bidNtceNo"),
                "공고명": item.get("bidNtceNm"),
                "수요기관": item.get("dminsttNm"),
                "게시일": item.get("bidNtceDt")
            })

        page += 1

    return pd.DataFrame(all_rows)

# ==================================================
# 5. 조회 + 조건 필터 + 정렬
# ==================================================

df_all = fetch_recent_bids()

if df_all.empty:
    print("ℹ 조회 결과 없음")
    exit(0)

df = df_all[
    df_all["수요기관"].astype(str).str.contains("|".join(AGENCIES), na=False)
    |
    df_all["공고명"].astype(str).str.contains("|".join(KEYWORDS), na=False)
].copy()

if df.empty:
    print("ℹ 조건 충족 공고 없음")
    exit(0)

df["게시일"] = pd.to_datetime(df["게시일"], errors="coerce")
df = df.sort_values("게시일", ascending=False).reset_index(drop=True)

# ==================================================
# 6. 메일 발송 (Gmail)
# ==================================================

msg = MIMEMultipart()
msg["From"] = GMAIL_USER
msg["To"] = MAIL_TO
msg["Subject"] = f"[나라장터] 최근 {DAYS}일 물품 입찰 공고"

body = df[["게시일", "수요기관", "공고명", "공고번호"]].to_string(index=False)
msg.attach(MIMEText(body, "plain", "utf-8"))

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(GMAIL_USER, GMAIL_APP_PW)
    server.send_message(msg)

print("📧 메일 발송 완료")
