from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from typing import List

app = FastAPI()

# in-memory queue (replace with DB/Redis in prod)
outgoing_sms_queue: List[dict] = []

class SMSRequest(BaseModel):
    number: str
    msg: str

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
        </body>
    </html>
    """

@app.post("/send_form")
async def send_form(number: str = Form(...), msg: str = Form(...)):
    outgoing_sms_queue.append({"number": number, "msg": msg})
    return RedirectResponse("/", status_code=303)
