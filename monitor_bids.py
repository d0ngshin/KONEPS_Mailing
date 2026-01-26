import os
import requests
import pandas as pd
from datetime import datetime, timedelta, date
import holidayskr
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import time

# ==================================================
# 1. 환경변수
# ==================================================
SERVICE_KEY = os.environ["SERVICE_KEY"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PW = os.environ["GMAIL_APP_PW"]
MAIL_TO = os.environ["MAIL_TO"]

KEYWORDS = ["복합기", "복사기", "사무기기", "사무용기기", "프린터"]
ROWS_PER_PAGE = 100

# ==================================================
# 2. 한국 공휴일 / 주말 제외
# ==================================================
today = date.today()
kr_holidays = holidayskr.year_holidays(today.year)

if today.weekday() >= 5 or today in kr_holidays:
    print("🚫 주말 또는 한국 공휴일 → 실행 종료")
    exit(0)

# ==================================================
# 3. 날짜 범위 (최근 3일)
# ==================================================
now = datetime.now()
inqryBgnDt = (now - timedelta(days=3)).strftime("%Y%m%d0000")
inqryEndDt = now.strftime("%Y%m%d2359")

# ==================================================
# 4. 입찰공고 (물품 + 용역)
# ==================================================
BID_BASE = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"
BID_ENDPOINTS = {
    "물품": "getBidPblancListInfoThngPPSSrch",
    "용역": "getBidPblancListInfoServcPPSSrch",
}

bid_rows = []

for biz_type, ep in BID_ENDPOINTS.items():
    for kw in KEYWORDS:
        page = 1
        while True:
            params = {
                "serviceKey": SERVICE_KEY,
                "pageNo": page,
                "numOfRows": ROWS_PER_PAGE,
                "inqryDiv": "1",
                "bidNtceNm": kw,
                "inqryBgnDt": inqryBgnDt,
                "inqryEndDt": inqryEndDt,
                "type": "json",
            }

            r = requests.get(f"{BID_BASE}/{ep}", params=params, timeout=10)

            if biz_type == "용역" and (not r.text or r.text.strip() == ""):
                break

            data = r.json()
            items = data.get("response", {}).get("body", {}).get("items", [])
            if not items:
                break

            for it in items:
                bid_rows.append({
                    "구분": "입찰공고",
                    "업무구분": biz_type,
                    "수요기관": it.get("dminsttNm"),
                    "사업명": it.get("bidNtceNm"),
                    "진행일자": it.get("bidNtceDt"),
                    "마감일자": it.get("bidClseDt"),
                    "금액": it.get("presmptPrce"),
                })

            page += 1
        time.sleep(0.2)

df_bid = pd.DataFrame(bid_rows)
if not df_bid.empty:
    df_bid["진행일자"] = pd.to_datetime(df_bid["진행일자"], errors="coerce")
    df_bid = df_bid.drop_duplicates(
        subset=["업무구분", "수요기관", "사업명", "마감일자"]
    ).sort_values("진행일자", ascending=False)

# ==================================================
# 5. 사전규격공개 (물품 + 용역)
# ==================================================
PRESPEC_BASE = "https://apis.data.go.kr/1230000/ao/HrcspSsstndrdInfoService"
PRESPEC_ENDPOINTS = {
    "물품": "getPublicPrcureThngInfoThngPPSSrch",
    "용역": "getPublicPrcureThngInfoServcPPSSrch",
}

prespec_rows = []

for biz_type, ep in PRESPEC_ENDPOINTS.items():
    for kw in KEYWORDS:
        params = {
            "serviceKey": SERVICE_KEY,
            "pageNo": 1,
            "numOfRows": ROWS_PER_PAGE,
            "inqryDiv": "1",
            "inqryBgnDt": inqryBgnDt,
            "inqryEndDt": inqryEndDt,
            "prdctClsfcNoNm": kw,
            "type": "json",
        }

        r = requests.get(f"{PRESPEC_BASE}/{ep}", params=params, timeout=10)
        data = r.json()
        items = data.get("response", {}).get("body", {}).get("items", [])

        for it in items:
            prespec_rows.append({
                "구분": "사전규격공개",
                "업무구분": biz_type,
                "수요기관": it.get("rlDminsttNm"),
                "사업명": it.get("prdctClsfcNoNm"),
                "진행일자": it.get("rcptDt"),
                "마감일자": it.get("dlvrTmlmtDt"),
                "금액": it.get("asignBdgtAmt"),
            })

        time.sleep(0.2)

df_prespec = pd.DataFrame(prespec_rows)
if not df_prespec.empty:
    df_prespec["진행일자"] = pd.to_datetime(df_prespec["진행일자"], errors="coerce")
    df_prespec = df_prespec.drop_duplicates(
        subset=["업무구분", "수요기관", "사업명", "진행일자"]
    ).sort_values("진행일자", ascending=False)

# ==================================================
# 6. 발주계획 (물품 + 용역)
# ==================================================
ORDER_BASE = "https://apis.data.go.kr/1230000/ao/OrderPlanSttusService"
ORDER_ENDPOINTS = {
    "물품": "getOrderPlanSttusListThngPPSSrch",
    "용역": "getOrderPlanSttusListServcPPSSrch",
}

order_rows = []

for biz_type, ep in ORDER_ENDPOINTS.items():
    for kw in KEYWORDS:
        params = {
            "serviceKey": SERVICE_KEY,
            "pageNo": 1,
            "numOfRows": ROWS_PER_PAGE,
            "inqryBgnDt": inqryBgnDt,
            "inqryEndDt": inqryEndDt,
            "bizNm": kw,
            "type": "json",
        }

        r = requests.get(f"{ORDER_BASE}/{ep}", params=params, timeout=10)
        data = r.json()
        items = data.get("response", {}).get("body", {}).get("items", [])

        for it in items:
            order_rows.append({
                "구분": "발주계획",
                "업무구분": biz_type,
                "수요기관": it.get("orderInsttNm"),
                "사업명": it.get("bizNm"),
                "진행일자": it.get("nticeDt"),
                "마감일자": None,
                "금액": it.get("sumOrderAmt"),
            })

        time.sleep(0.2)

df_order = pd.DataFrame(order_rows)
if not df_order.empty:
    df_order["진행일자"] = pd.to_datetime(df_order["진행일자"], errors="coerce")
    df_order = df_order.drop_duplicates(
        subset=["업무구분", "수요기관", "사업명", "진행일자"]
    ).sort_values("진행일자", ascending=False)

# ==================================================
# 7. 메일 발송
# ==================================================
msg = MIMEMultipart()
msg["From"] = GMAIL_USER
msg["To"] = MAIL_TO
msg["Subject"] = f"[나라장터] 입찰·사전규격·발주계획 알림 ({now.strftime('%Y-%m-%d %H:%M')})"

body = ""
if not df_bid.empty:
    body += "\n[입찰공고]\n" + df_bid.reset_index(drop=True).to_string(index=False) + "\n"
if not df_prespec.empty:
    body += "\n[사전규격공개]\n" + df_prespec.reset_index(drop=True).to_string(index=False) + "\n"
if not df_order.empty:
    body += "\n[발주계획]\n" + df_order.reset_index(drop=True).to_string(index=False) + "\n"

if body.strip() == "":
    print("ℹ 전송할 데이터 없음")
    exit(0)

msg.attach(MIMEText(body, "plain", "utf-8"))

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(GMAIL_USER, GMAIL_APP_PW)
    server.send_message(msg)

print("📧 메일 발송 완료")
