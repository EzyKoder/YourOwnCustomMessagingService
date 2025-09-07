from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from typing import List
import random, string, time

app = FastAPI()

# ---------- In-memory stores ----------
# Outgoing SMS queue (replace with DB/Redis in prod)
outgoing_sms_queue: List[dict] = []

# OTPs: {phone: {"otp": "123456", "expires": timestamp}}
otp_store = {}

# Verified users: {phone: uidstring}
verified_users = {}

# ---------- Models ----------
class SMSRequest(BaseModel):
    number: str
    msg: str

# ---------- Utilities ----------
def generate_uid():
    """Generate a Firebase-style 28-char alphanumeric UID."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=28))

# ---------- Endpoints ----------

@app.post("/queue_sms")
async def queue_sms(sms: SMSRequest):
    outgoing_sms_queue.append({"number": sms.number, "msg": sms.msg})
    return {"status": "queued", "to": sms.number, "msg": sms.msg}

@app.get("/get_sms")
async def get_sms():
    if outgoing_sms_queue:
        return outgoing_sms_queue.pop(0)
    return {"status": "empty"}

@app.post("/receive_sms")
async def receive_sms(data: dict):
    print(f"📥 Incoming SMS from {data.get('from')}: {data.get('msg')}")
    return {"status": "received"}

# ✅ Simple HTML Form to send SMS
@app.get("/", response_class=HTMLResponse)
async def form_page():
    return """
    <html>
        <head><title>SMS Gateway</title></head>
        <body>
            <h2>📡 Send SMS</h2>
            <form action="/send_form" method="post">
                <label>Phone Number:</label>
                <input type="text" name="number" required><br><br>
                <label>Message:</label>
                <textarea name="msg" rows="4" cols="30" required></textarea><br><br>
                <button type="submit">Send SMS</button>
            </form>
            <hr>
            <h3>OTP Demo</h3>
            <form action="/request_otp_form" method="post">
                <label>Phone Number:</label>
                <input type="text" name="number" required>
                <button type="submit">Request OTP</button>
            </form>
            <br>
            <form action="/verify_otp_form" method="post">
                <label>Phone Number:</label>
                <input type="text" name="number" required><br><br>
                <label>OTP:</label>
                <input type="text" name="otp" required><br><br>
                <button type="submit">Verify OTP</button>
            </form>
        </body>
    </html>
    """

@app.post("/send_form")
async def send_form(number: str = Form(...), msg: str = Form(...)):
    outgoing_sms_queue.append({"number": number, "msg": msg})
    return RedirectResponse("/", status_code=303)

# ---------- OTP API ----------

@app.post("/request_otp")
async def request_otp(sms: SMSRequest):
    """API: Request an OTP to be sent."""
    otp = ''.join(random.choices(string.digits, k=6))
    expiry = time.time() + 300  # 5 min validity
    otp_store[sms.number] = {"otp": otp, "expires": expiry}

    # queue SMS to actually send OTP
    outgoing_sms_queue.append({"number": sms.number, "msg": f"Your OTP is {otp}"})
    return {"status": "otp_sent", "to": sms.number}

@app.post("/verify_otp")
async def verify_otp(data: dict):
    """API: Verify OTP and return UID."""
    phone = data.get("number")
    otp = data.get("otp")
    record = otp_store.get(phone)
    if not record:
        return {"status": "failed", "reason": "no otp requested"}
    if time.time() > record["expires"]:
        return {"status": "failed", "reason": "otp expired"}
    if otp != record["otp"]:
        return {"status": "failed", "reason": "invalid otp"}

    uid = verified_users.get(phone)
    if not uid:
        uid = generate_uid()
        verified_users[phone] = uid
    otp_store.pop(phone, None)
    return {"status": "verified", "uid": uid}

# ---------- OTP HTML helpers ----------
@app.post("/request_otp_form")
async def request_otp_form(number: str = Form(...)):
    otp = ''.join(random.choices(string.digits, k=6))
    expiry = time.time() + 300
    otp_store[number] = {"otp": otp, "expires": expiry}
    outgoing_sms_queue.append({"number": number, "msg": f"Your OTP is {otp}"})
    return RedirectResponse("/", status_code=303)

@app.post("/verify_otp_form")
async def verify_otp_form(number: str = Form(...), otp: str = Form(...)):
    record = otp_store.get(number)
    if not record or time.time() > record["expires"] or otp != record["otp"]:
        return HTMLResponse("<h3>OTP verification failed</h3>")
    uid = verified_users.get(number)
    if not uid:
        uid = generate_uid()
        verified_users[number] = uid
    otp_store.pop(number, None)
    return HTMLResponse(f"<h3>OTP verified. UID: {uid}</h3>")
