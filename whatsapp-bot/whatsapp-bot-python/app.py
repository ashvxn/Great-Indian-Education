# --- IMPORTS ---
import os
import requests
import pymysql
from flask import Flask, request, make_response
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
app = Flask(__name__)

# ===========================================================================
# BOT 1 — Great Indian Academy (existing, unchanged)
# ===========================================================================

ACCESS_TOKEN    = os.getenv('ACCESS_TOKEN')
PHONE_NUMBER_ID = os.getenv('PHONE_NUMBER_ID')
VERIFY_TOKEN    = os.getenv('VERIFY_TOKEN')

DB_CONFIG = {
    'host':        os.getenv('DB_HOST'),
    'port':        int(os.getenv('DB_PORT', 3306)),
    'user':        os.getenv('DB_USER'),
    'password':    os.getenv('DB_PASSWORD'),
    'database':    os.getenv('DB_NAME'),
    'charset':     'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'connect_timeout': 10,
}

COMPANY_ID = 4          # Bot 1 — Great Indian Academy

# ===========================================================================
# BOT 2 — IMTTC (new bot)
# ===========================================================================

ACCESS_TOKEN_2    = os.getenv('ACCESS_TOKEN_2')
PHONE_NUMBER_ID_2 = os.getenv('PHONE_NUMBER_ID_2')
VERIFY_TOKEN_2    = os.getenv('VERIFY_TOKEN_2')

COMPANY_ID_2 = 7        # ← Change this to the correct COMPANY_ID for IMTTC

# ===========================================================================
# SESSION STORES (kept separate per bot)
# ===========================================================================

sessions  = {}   # Bot 1
sessions2 = {}   # Bot 2


# ---------------------------------------------------------------------------
# DATABASE — shared helper, accepts company_id as param
# ---------------------------------------------------------------------------

def save_lead(name, phone, interest, source_note, company_id=COMPANY_ID):
    note = f"Enquired via WhatsApp bot — {source_note}"
    now  = datetime.now()
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:

            cursor.execute(
                "SELECT lead_id FROM leads WHERE phone = %s AND company_id = %s LIMIT 1",
                (phone, company_id)
            )
            existing = cursor.fetchone()

            if existing:
                lead_id = existing['lead_id']
                cursor.execute(
                    """UPDATE lead_updates
                       SET notes = CONCAT(COALESCE(notes, ''), '\n', %s), updated_at = %s
                       WHERE lead_id = %s AND company_id = %s""",
                    (f"Re-enquired via WhatsApp — {source_note}", now, lead_id, company_id)
                )
            else:
                cursor.execute(
                    """INSERT INTO leads
                           (company_id, name, phone, location, source, notes, status, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (company_id, name, phone, 'Kochi, Kerala, India', 'WhatsApp', note, 'New', now, now)
                )
                lead_id = cursor.lastrowid

                cursor.execute(
                    """INSERT INTO lead_updates
                           (company_id, lead_id, updated_by, notes, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (company_id, lead_id, 1, note, now, now)
                )

        conn.commit()
    except Exception as e:
        print(f"❌ DB Error: {e}")
    finally:
        try:
            conn.close()
        except:
            pass


# ===========================================================================
# WHATSAPP SENDERS — Bot 1
# ===========================================================================

def _post(payload, access_token=None, phone_number_id=None):
    _token = access_token or ACCESS_TOKEN
    _pid   = phone_number_id or PHONE_NUMBER_ID
    url    = f"https://graph.facebook.com/v21.0/{_pid}/messages"
    headers = {
        "Authorization": f"Bearer {_token}",
        "Content-Type":  "application/json",
    }
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        print(f"❌ Send Error: {resp.text}")


def send_text(to, body, access_token=None, phone_number_id=None):
    _post({
        "messaging_product": "whatsapp",
        "to":   to,
        "type": "text",
        "text": {"body": body},
    }, access_token, phone_number_id)


def send_buttons(to, body_text, buttons, access_token=None, phone_number_id=None):
    _post({
        "messaging_product": "whatsapp",
        "to":   to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                    for b in buttons[:3]
                ]
            },
        },
    }, access_token, phone_number_id)


def send_list(to, body_text, button_label, sections, access_token=None, phone_number_id=None):
    MAX_ROWS    = 10
    total_rows  = 0
    trimmed_sections = []

    for section in sections:
        rows         = section.get("rows", [])
        allowed_rows = []
        for row in rows:
            if total_rows < MAX_ROWS:
                allowed_rows.append(row)
                total_rows += 1
            else:
                break
        if allowed_rows:
            trimmed_sections.append({"title": section.get("title"), "rows": allowed_rows})
        if total_rows >= MAX_ROWS:
            break

    print(f"📊 Rows sent: {total_rows}")

    _post({
        "messaging_product": "whatsapp",
        "to":   to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body_text},
            "action": {
                "button":   button_label,
                "sections": trimmed_sections,
            },
        },
    }, access_token, phone_number_id)


def send_typing_indicator(to, message_id, access_token=None, phone_number_id=None):
    _post({
        "messaging_product": "whatsapp",
        "status":     "read",
        "message_id": message_id,
        "typing_indicator": {"type": "text"}
    }, access_token, phone_number_id)


# ===========================================================================
# BOT 1 FLOW — Great Indian Academy (100% unchanged)
# ===========================================================================

def send_welcome(to):
    send_buttons(
        to,
        "👋 Welcome to *Great Indian Academy*, Kochi!\n\n"
        "We offer professional teacher training courses — Diploma, PG Diploma & Certificate programmes in Montessori, Early Childhood Care, Special Education and Management Studies.\n\n"
        "How can I help you today?",
        [
            {"id": "explore_courses",   "title": "📚 Explore Courses"},
            {"id": "faq_main",          "title": "❓ Have a Question"},
            {"id": "talk_counsellor",   "title": "🎓 Talk to Counsellor"},
        ],
    )

def send_course_menu(to):
    send_list(
        to,
        "🎓 *Our Courses & Specialisations*\n\n"
        "We offer programmes from Certificate to PG Diploma level. Choose a category to know more:",
        "View Courses",
        [
            {
                "title": "By Specialisation",
                "rows": [
                    {"id": "course_montessori",  "title": "Montessori",          "description": "Diploma & PG Diploma"},
                    {"id": "course_ecce",         "title": "Early Childhood Care", "description": "Diploma & PG Diploma"},
                    {"id": "course_special_edu",  "title": "Special Education",    "description": "Diploma & PG Diploma"},
                    {"id": "course_management",   "title": "Management Studies",   "description": "Diploma & PG Diploma"},
                ],
            },
            {
                "title": "By Level",
                "rows": [
                    {"id": "course_diploma",     "title": "Diploma",     "description": "1 year / 6-month fast-track"},
                    {"id": "course_pgdiploma",   "title": "PG Diploma",  "description": "2 years / 12-month fast-track"},
                    {"id": "course_certificate", "title": "Certificate", "description": "Short-term programmes"},
                ],
            },
        ],
    )

def send_course_detail(to, course_id):
    details = {
        "course_montessori": (
            "🌱 *Montessori Method of Education*\n\n"
            "Learn the globally respected Montessori approach to child-centred education.\n\n"
            "📌 *Levels:* Diploma & PG Diploma\n"
            "⏳ *Duration:* 1 year (Diploma) | 2 years / 12-month fast-track (PG Diploma)\n"
            "💰 *Fees:* ₹12,000 – ₹85,000 depending on level & mode\n"
            "📖 *Eligibility:* 10+2 for Diploma | Bachelor's degree for PG Diploma"
        ),
        "course_ecce": (
            "👶 *Early Childhood Care & Education (ECCE)*\n\n"
            "Specialise in nurturing and educating children in their most critical developmental years.\n\n"
            "📌 *Levels:* Diploma & PG Diploma\n"
            "⏳ *Duration:* 1 year (Diploma) | 2 years / 12-month fast-track (PG Diploma)\n"
            "💰 *Fees:* ₹12,000 – ₹85,000 depending on level & mode\n"
            "📖 *Eligibility:* 10+2 for Diploma | Bachelor's degree for PG Diploma"
        ),
        "course_special_edu": (
            "🤝 *Special Education*\n\n"
            "Equip yourself to support children with diverse learning needs.\n\n"
            "📌 *Levels:* Diploma & PG Diploma\n"
            "⏳ *Duration:* 1 year (Diploma) | 2 years / 12-month fast-track (PG Diploma)\n"
            "💰 *Fees:* ₹12,000 – ₹85,000 depending on level & mode\n"
            "📖 *Eligibility:* 10+2 for Diploma | Bachelor's degree for PG Diploma"
        ),
        "course_management": (
            "📊 *Management Studies*\n\n"
            "Build leadership and management skills tailored for educational institutions.\n\n"
            "📌 *Levels:* Diploma & PG Diploma\n"
            "⏳ *Duration:* 1 year (Diploma) | 2 years / 12-month fast-track (PG Diploma)\n"
            "💰 *Fees:* ₹12,000 – ₹85,000 depending on level & mode\n"
            "📖 *Eligibility:* 10+2 for Diploma | Bachelor's degree for PG Diploma"
        ),
        "course_diploma": (
            "📜 *Diploma Courses*\n\n"
            "One-year programmes (or 6-month fast-track) in Montessori, ECCE, Special Education & Management.\n\n"
            "📖 *Eligibility:* 10+2 (Higher Secondary) pass from a recognised board\n"
            "💰 *Fees:* Starting from ₹12,000\n"
            "🎓 *Certificate:* Diploma certificate, valid for lifetime"
        ),
        "course_pgdiploma": (
            "🎓 *PG Diploma Courses*\n\n"
            "Two-year programmes (or 12-month fast-track) for deeper specialisation.\n\n"
            "📖 *Eligibility:* Bachelor's degree in any discipline\n"
            "💰 *Fees:* Up to ₹85,000\n"
            "🎓 *Certificate:* PG Diploma certificate, valid for lifetime\n"
            "✅ Internationally recognised & verifiable"
        ),
        "course_certificate": (
            "📋 *Certificate Courses*\n\n"
            "Short-term programmes to quickly build or validate your teaching skills.\n\n"
            "📖 *Eligibility:* 10+2 pass\n"
            "💰 *Fees:* Starting from ₹12,000\n"
            "⏳ *Duration:* Short-term, flexible schedule available"
        ),
    }
    msg = details.get(course_id, "Details coming soon. Please contact us for more information.")
    send_text(to, msg)


def send_faq_menu(to):
    send_list(
        to,
        "❓ *What would you like to know?*\n\nSelect a topic below:",
        "Choose a Topic",
        [
            {
                "title": "Courses & Eligibility",
                "rows": [
                    {"id": "faq_eligibility", "title": "Eligibility",      "description": "Who can apply?"},
                    {"id": "faq_duration",    "title": "Course Duration",  "description": "How long are courses?"},
                    {"id": "faq_modes",       "title": "Study Modes",      "description": "Online, offline, hybrid?"},
                    {"id": "faq_weekend",     "title": "Weekend Batches",  "description": "For working professionals"},
                ],
            },
            {
                "title": "Certificates & Validity",
                "rows": [
                    {"id": "faq_certificate",  "title": "Certificate Type",     "description": "What do you get?"},
                    {"id": "faq_validity",     "title": "Certificate Validity",  "description": "How long is it valid?"},
                    {"id": "faq_online_valid", "title": "Online Courses Valid?", "description": "Acceptance & recognition"},
                    {"id": "faq_aided",        "title": "Aided School Jobs?",    "description": "Govt / aided school jobs"},
                ],
            },
            {
                "title": "Fees & Placements",
                "rows": [
                    {"id": "faq_fees",        "title": "Fee Structure",    "description": "How much does it cost?"},
                    {"id": "faq_installment", "title": "Instalment Options","description": "Pay in parts?"},
                    {"id": "faq_placements",  "title": "Placement Help",   "description": "Career support"},
                    {"id": "faq_abroad",      "title": "Jobs Abroad",      "description": "International placements"},
                ],
            },
            {
                "title": "Other",
                "rows": [
                    {"id": "faq_location", "title": "Our Location",    "description": "Where are you located?"},
                    {"id": "faq_language", "title": "Language Classes", "description": "English & language classes"},
                    {"id": "faq_recorded", "title": "Missed Classes?",  "description": "Can I catch up later?"},
                ],
            },
        ],
    )

FAQ_ANSWERS = {
    "faq_eligibility": (
        "📋 *Eligibility to Join*\n\n"
        "• *Diploma courses:* Minimum 10+2 (Higher Secondary) pass from any recognised board.\n"
        "• *PG Diploma courses:* A Bachelor's degree in any discipline.\n\n"
        "Both freshers and experienced teachers are welcome."
    ),
    "faq_duration": (
        "⏳ *Course Duration*\n\n"
        "• *Diploma:* 1 year\n"
        "• *PG Diploma:* 2 years\n\n"
        "Both available in:\n"
        "• ⚡ *Fast-track:* 6 months\n"
        "• 🗓 *Regular:* 12 months"
    ),
    "faq_modes": (
        "📡 *Modes of Study*\n\n"
        "1️⃣ *Offline* — Face-to-face classes at our Kochi centre.\n\n"
        "2️⃣ *Online* — Live sessions via Google Meet / Zoom.\n\n"
        "3️⃣ *Self-Paced* — Access materials at your own speed.\n\n"
        "4️⃣ *Hybrid* — Live online + occasional centre visits."
    ),
    "faq_weekend": (
        "📅 *Weekend & Holiday Batches*\n\n"
        "Yes! Saturday & Sunday batches available for working professionals."
    ),
    "faq_certificate": (
        "🎓 *Type of Certificate*\n\n"
        "We award *Diploma Certificates* — internationally recognised and verifiable anytime."
    ),
    "faq_validity": (
        "✅ *Certificate Validity*\n\n"
        "Our certifications are valid for a *lifetime* — no renewals, no expiry."
    ),
    "faq_online_valid": (
        "🌐 *Are Online Courses Valid?*\n\n"
        "Yes! Our online programmes are accepted by schools and educational organisations worldwide."
    ),
    "faq_aided": (
        "🏫 *Certificates for Aided Schools*\n\n"
        "Conditional approvals apply for aided school appointments. Speak to our counsellor for guidance specific to your case."
    ),
    "faq_fees": (
        "💰 *Fee Structure*\n\n"
        "• *Certificate:* From ₹12,000\n"
        "• *Diploma:* ₹12,000 – ₹40,000\n"
        "• *PG Diploma:* Up to ₹85,000\n\n"
        "All fees include materials, exams, certification & practical workshops."
    ),
    "faq_installment": (
        "🏦 *Instalment Options*\n\n"
        "Yes! Easy instalments available — no hidden charges."
    ),
    "faq_placements": (
        "💼 *Placement Support*\n\n"
        "• Internships at partner schools\n"
        "• Interview preparation\n"
        "• NEP 2020 aligned certifications\n"
        "• Placement assistance is *free*."
    ),
    "faq_abroad": (
        "✈️ *Jobs Abroad*\n\n"
        "Our candidates find global opportunities via our student network and direct walk-ins to international schools."
    ),
    "faq_location": (
        "📍 *Location*\n\n"
        "We are located in *Kochi, Kerala, India*.\n\nContact us for exact address and directions!"
    ),
    "faq_language": (
        "🗣 *Language Improvement Classes*\n\n"
        "Yes! Contact us directly for schedule, fees, and availability."
    ),
    "faq_recorded": (
        "🎥 *Missed Classes*\n\n"
        "• *Self-Paced:* Access materials anytime via your login.\n"
        "• *Hybrid:* Live sessions + mentor guidance available."
    ),
}


def prompt_for_name(to, context=""):
    context_msg = f" about *{context}*" if context else ""
    send_text(
        to,
        f"I'd love to connect you with our counsellor{context_msg}! 😊\n\n"
        "Could you please share your *name*?"
    )

def confirm_lead_and_save(to, session, company_id=COMPANY_ID):
    name     = session.get('name', 'there')
    interest = session.get('interest', 'our courses')
    save_lead(name, to, interest, f"Interest in {interest}", company_id)
    session['lead_saved'] = True
    sessions[to] = session
    send_buttons(
        to,
        f"✅ Thank you, *{name}*!\n\n"
        f"Our counsellor will reach out to you shortly regarding *{interest}*.\n\n"
        "Is there anything else I can help you with?",
        [
            {"id": "faq_main",        "title": "❓ More Questions"},
            {"id": "explore_courses", "title": "📚 View Courses"},
            {"id": "end_chat",        "title": "👍 That's All"},
        ],
    )

def offer_counsellor(to, topic_label):
    send_buttons(
        to,
        "Would you like to know more or speak with a counsellor?",
        [
            {"id": f"counsellor_yes|{topic_label[:20]}", "title": "🎓 Talk to Counsellor"},
            {"id": "faq_main",                           "title": "❓ More Questions"},
            {"id": "explore_courses",                    "title": "📚 View Courses"},
        ],
    )

def handle_text(sender, text, session):
    state = session.get('state', 'initial')

    if state == 'awaiting_name':
        name = text.strip().title()
        if len(name) < 2:
            send_text(sender, "Please enter your full name so we can address you correctly. 😊")
            return
        session['name']  = name
        session['state'] = 'done'
        sessions[sender] = session
        confirm_lead_and_save(sender, session)

    elif state == 'awaiting_name_course':
        name = text.strip().title()
        if len(name) < 2:
            send_text(sender, "Please enter your full name. 😊")
            return
        session['name']  = name
        session['state'] = 'done'
        sessions[sender] = session
        confirm_lead_and_save(sender, session)

    else:
        sessions[sender] = {'state': 'initial'}
        send_welcome(sender)


def handle_button_or_list(sender, item_id, session):

    if item_id == 'explore_courses':
        session['state'] = 'browsing'
        sessions[sender] = session
        send_course_menu(sender)
        return

    if item_id == 'faq_main':
        session['state'] = 'browsing'
        sessions[sender] = session
        send_faq_menu(sender)
        return

    if item_id == 'talk_counsellor':
        session['state']    = 'awaiting_name'
        session['interest'] = 'teacher training courses'
        sessions[sender]    = session
        prompt_for_name(sender)
        return

    if item_id == 'end_chat':
        sessions[sender] = {'state': 'initial'}
        send_text(
            sender,
            "Thank you for reaching out to *Great Indian Academy*! 🎓\n\n"
            "We wish you all the best in your teaching journey. Feel free to message us anytime. 😊"
        )
        return

    if item_id.startswith('course_'):
        send_course_detail(sender, item_id)
        session['interest'] = item_id.replace('course_', '').replace('_', ' ').title()
        sessions[sender]    = session
        send_buttons(
            sender,
            "Would you like to apply or speak with a counsellor about this course?",
            [
                {"id": f"counsellor_yes|{session['interest'][:20]}", "title": "🎓 Talk to Counsellor"},
                {"id": "explore_courses",                            "title": "📚 Other Courses"},
                {"id": "faq_main",                                   "title": "❓ Have a Question"},
            ],
        )
        return

    if item_id in FAQ_ANSWERS:
        send_text(sender, FAQ_ANSWERS[item_id])
        topic_label      = item_id.replace('faq_', '').replace('_', ' ').title()
        high_intent_faqs = {'faq_fees', 'faq_installment', 'faq_placements', 'faq_abroad', 'faq_aided'}
        if item_id in high_intent_faqs:
            session['interest'] = topic_label
            sessions[sender]    = session
            send_buttons(
                sender,
                "Would you like personalised guidance on this?",
                [
                    {"id": f"counsellor_yes|{topic_label[:20]}", "title": "🎓 Talk to Counsellor"},
                    {"id": "faq_main",                           "title": "❓ More Questions"},
                    {"id": "explore_courses",                    "title": "📚 View Courses"},
                ],
            )
        else:
            offer_counsellor(sender, topic_label)
        return

    if item_id.startswith('counsellor_yes'):
        parts    = item_id.split('|', 1)
        interest = parts[1] if len(parts) > 1 else session.get('interest', 'our courses')
        session['state']    = 'awaiting_name'
        session['interest'] = interest
        sessions[sender]    = session
        prompt_for_name(sender, interest)
        return

    sessions[sender] = {'state': 'initial'}
    send_welcome(sender)


# ---------------------------------------------------------------------------
# Bot 1 — Webhook routes
# ---------------------------------------------------------------------------

@app.route('/webhook', methods=['GET'])
def verify():
    mode      = request.args.get('hub.mode')
    token     = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print("✅ Bot1 Webhook Verified!")
        return challenge, 200
    return "Verification failed", 403


@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    try:
        entry    = data.get('entry', [{}])[0]
        changes  = entry.get('changes', [{}])[0]
        value    = changes.get('value', {})
        messages = value.get('messages', [])

        if not messages:
            return make_response("EVENT_RECEIVED", 200)

        message  = messages[0]
        sender   = message.get('from')
        msg_type = message.get('type')
        msg_id   = message.get('id')
        session  = sessions.get(sender, {'state': 'initial'})

        if msg_id:
            send_typing_indicator(sender, msg_id)

        print(f"📩 [Bot1] [{msg_type}] from {sender} | state: {session.get('state')}")

        if msg_type == 'text':
            text = message.get('text', {}).get('body', '').strip()
            handle_text(sender, text, session)

        elif msg_type == 'interactive':
            interactive = message.get('interactive', {})
            itype       = interactive.get('type')
            if itype == 'button_reply':
                handle_button_or_list(sender, interactive['button_reply']['id'], session)
            elif itype == 'list_reply':
                handle_button_or_list(sender, interactive['list_reply']['id'], session)

        elif msg_type in ('image', 'document', 'audio', 'video', 'sticker'):
            send_text(sender, "Thank you for your message! 😊 I can only process text right now.\n\nPlease type *Hi* to get back to the menu.")
            sessions[sender] = {'state': 'initial'}
            send_welcome(sender)

    except Exception as e:
        print(f"❌ Bot1 Webhook Error: {e}")

    return make_response("EVENT_RECEIVED", 200)


# ===========================================================================
# BOT 2 — IMTTC Flow
# ===========================================================================

# ---------------------------------------------------------------------------
# Bot 2 — helpers (all pass ACCESS_TOKEN_2 / PHONE_NUMBER_ID_2)
# ---------------------------------------------------------------------------

def b2_send_text(to, body):
    send_text(to, body, ACCESS_TOKEN_2, PHONE_NUMBER_ID_2)

def b2_send_buttons(to, body_text, buttons):
    send_buttons(to, body_text, buttons, ACCESS_TOKEN_2, PHONE_NUMBER_ID_2)

def b2_send_list(to, body_text, button_label, sections):
    send_list(to, body_text, button_label, sections, ACCESS_TOKEN_2, PHONE_NUMBER_ID_2)


# ---------------------------------------------------------------------------
# Bot 2 — Welcome
# ---------------------------------------------------------------------------

def b2_send_welcome(to):
    b2_send_buttons(
        to,
        "👋 Welcome to *IMTTC – International Montessori Teacher Training Centre*!\n\n"
        "🌍 Build your career in teaching with globally recognized courses.\n\n"
        "Please choose an option below 👇",
        [
            {"id": "b2_courses",     "title": "📚 Course Details"},
            {"id": "b2_admission",   "title": "📝 Admission Process"},
            {"id": "b2_fees",        "title": "💰 Fees & Duration"},
        ],
    )
    # WhatsApp only allows 3 buttons, so send a second message for remaining options
    b2_send_buttons(
        to,
        "More options 👇",
        [
            {"id": "b2_career",      "title": "💼 Career Opportunities"},
            {"id": "b2_counsellor",  "title": "🎓 Talk to Counselor"},
        ],
    )


# ---------------------------------------------------------------------------
# Bot 2 — Course menu & details
# ---------------------------------------------------------------------------

B2_COURSES = {
    "b2_course_idim": (
        "🎓 *International Diploma in Montessori (IDIM)*\n\n"
        "A globally recognised diploma covering the full Montessori philosophy and practice.\n\n"
        "📅 *Duration:* 6 months – 1 year\n"
        "📖 *Eligibility:* 10+2 pass\n"
        "💰 *Fees:* Flexible payment options available\n"
        "✅ Internationally recognised certificate"
    ),
    "b2_course_bdim": (
        "🎓 *Bachelor Diploma in Montessori (BDIM)*\n\n"
        "An advanced bachelor-level programme for deeper mastery of Montessori education.\n\n"
        "📅 *Duration:* 1 year\n"
        "📖 *Eligibility:* 10+2 pass\n"
        "💰 *Fees:* Flexible payment options available\n"
        "✅ Internationally recognised certificate"
    ),
    "b2_course_mdim": (
        "🎓 *Master Diploma in Montessori (MDIM)*\n\n"
        "Our flagship master-level programme for experienced educators seeking the highest credential.\n\n"
        "📅 *Duration:* 1 year\n"
        "📖 *Eligibility:* Bachelor's degree\n"
        "💰 *Fees:* Flexible payment options available\n"
        "✅ Internationally recognised certificate"
    ),
    "b2_course_ld": (
        "🤝 *Diploma in Learning Disability & Inclusive Education*\n\n"
        "Equip yourself to support children with diverse and special learning needs.\n\n"
        "📅 *Duration:* 6 months – 1 year\n"
        "📖 *Eligibility:* 10+2 pass\n"
        "💰 *Fees:* Flexible payment options available"
    ),
    "b2_course_ecce": (
        "👶 *Advanced & PG Diploma in Early Childhood Care*\n\n"
        "Specialise in nurturing children in their most critical early years.\n\n"
        "📅 *Duration:* 6 months – 1 year\n"
        "📖 *Eligibility:* 10+2 for Diploma | Bachelor's for PG Diploma\n"
        "💰 *Fees:* Flexible payment options available"
    ),
}

def b2_send_course_menu(to):
    b2_send_list(
        to,
        "📖 *We offer the following courses:*\n\nSelect one to learn more 👇",
        "View Courses",
        [
            {
                "title": "Montessori Programmes",
                "rows": [
                    {"id": "b2_course_idim", "title": "IDIM",  "description": "International Diploma in Montessori"},
                    {"id": "b2_course_bdim", "title": "BDIM",  "description": "Bachelor Diploma in Montessori"},
                    {"id": "b2_course_mdim", "title": "MDIM",  "description": "Master Diploma in Montessori"},
                ],
            },
            {
                "title": "Specialist Programmes",
                "rows": [
                    {"id": "b2_course_ld",   "title": "Learning Disability", "description": "Inclusive Education Diploma"},
                    {"id": "b2_course_ecce", "title": "Early Childhood Care", "description": "Advanced & PG Diploma"},
                ],
            },
        ],
    )

def b2_send_course_detail(to, course_id, session):
    msg = B2_COURSES.get(course_id, "Details coming soon. Please contact us for more information.")
    b2_send_text(to, msg)
    course_name = course_id.replace('b2_course_', '').upper()
    session['interest'] = course_name
    sessions2[to] = session
    b2_send_buttons(
        to,
        "Great choice 👍\n\nWould you like to know more about:",
        [
            {"id": f"b2_syllabus|{course_id}",  "title": "📋 Syllabus"},
            {"id": f"b2_career_scope|{course_id}", "title": "💼 Career Scope"},
            {"id": "b2_counsellor",              "title": "🎓 Talk to Counselor"},
        ],
    )


# ---------------------------------------------------------------------------
# Bot 2 — Admission
# ---------------------------------------------------------------------------

def b2_send_admission(to):
    b2_send_text(
        to,
        "📝 *Admission Process*\n\n"
        "It's simple and quick!\n\n"
        "✔️ Fill the application form\n"
        "✔️ Submit your documents\n"
        "✔️ Confirm your seat\n"
        "✔️ Start your course!\n\n"
        "🚀 *Admissions Open for 2026–27*\n\n"
        "Limited seats available — don't miss out!"
    )
    b2_send_buttons(
        to,
        "Would you like us to send the application form?",
        [
            {"id": "b2_apply_yes", "title": "✅ Yes, Send Form"},
            {"id": "b2_courses",   "title": "📚 View Courses"},
            {"id": "b2_counsellor","title": "🎓 Talk to Counselor"},
        ],
    )


# ---------------------------------------------------------------------------
# Bot 2 — Fees
# ---------------------------------------------------------------------------

def b2_send_fees(to):
    b2_send_text(
        to,
        "💰 *Fees & Duration*\n\n"
        "📅 *Duration:* 3 months – 1 year (depending on the programme)\n\n"
        "🎁 *Flexible payment options available* — no need to pay the full amount upfront!\n\n"
        "Fees vary based on the course level and mode of study."
    )
    b2_send_buttons(
        to,
        "What would you like to know?",
        [
            {"id": "b2_fees_exact",        "title": "💲 Exact Fee Details"},
            {"id": "b2_fees_emi",          "title": "🏦 EMI Options"},
            {"id": "b2_fees_scholarship",  "title": "🎁 Scholarships"},
        ],
    )


# ---------------------------------------------------------------------------
# Bot 2 — Career
# ---------------------------------------------------------------------------

def b2_send_career(to):
    b2_send_text(
        to,
        "💼 *Career Opportunities After IMTTC*\n\n"
        "Our graduates go on to work as:\n\n"
        "👩‍🏫 Montessori Teacher\n"
        "🌍 International School Educator\n"
        "🧠 Special Educator\n"
        "🏫 Preschool Owner / Manager\n"
        "✈️ Opportunities abroad\n\n"
        "We provide personalised placement guidance — completely *free of charge*."
    )
    b2_send_buttons(
        to,
        "Want guidance for placements?",
        [
            {"id": "b2_placement_yes", "title": "✅ Yes, Guide Me"},
            {"id": "b2_courses",       "title": "📚 View Courses"},
            {"id": "b2_counsellor",    "title": "🎓 Talk to Counselor"},
        ],
    )


# ---------------------------------------------------------------------------
# Bot 2 — Lead capture (multi-step: name → location → qualification)
# ---------------------------------------------------------------------------

def b2_prompt_name(to, context=""):
    context_msg = f" about *{context}*" if context else ""
    b2_send_text(
        to,
        f"I'd love to connect you with our counsellor{context_msg}! 😊\n\n"
        "Could you please share your *full name*? 👤"
    )

def b2_confirm_lead(to, session):
    name  = session.get('name', 'there')
    interest = session.get('interest', 'our courses')
    save_lead(name, to, interest, f"IMTTC — Interest in {interest}", COMPANY_ID_2)
    session['lead_saved'] = True
    sessions2[to] = session
    b2_send_buttons(
        to,
        f"✅ Thank you, *{name}*!\n\n"
        f"Our academic counsellor will reach out to you shortly regarding *{interest}*.\n\n"
        "Is there anything else I can help you with?",
        [
            {"id": "b2_courses",    "title": "📚 View Courses"},
            {"id": "b2_career",     "title": "💼 Career Info"},
            {"id": "b2_end_chat",   "title": "👍 That's All"},
        ],
    )


# ---------------------------------------------------------------------------
# Bot 2 — Counsellor call time preference
# ---------------------------------------------------------------------------

def b2_ask_call_time(to):
    b2_send_buttons(
        to,
        "📞 Our academic counsellor will contact you shortly!\n\n"
        "What is your preferred time to call?",
        [
            {"id": "b2_time_morning",   "title": "🌅 Morning"},
            {"id": "b2_time_afternoon", "title": "☀️ Afternoon"},
            {"id": "b2_time_evening",   "title": "🌙 Evening"},
        ],
    )


# ---------------------------------------------------------------------------
# Bot 2 — Qualification qualifier
# ---------------------------------------------------------------------------

def b2_ask_qualifier(to):
    b2_send_buttons(
        to,
        "Just a couple of quick questions to guide you better 😊\n\n"
        "Are you currently working?",
        [
            {"id": "b2_working_yes", "title": "✅ Yes"},
            {"id": "b2_working_no",  "title": "❌ No"},
        ],
    )

def b2_ask_mode(to):
    b2_send_buttons(
        to,
        "What is your preferred mode of study?",
        [
            {"id": "b2_mode_online",  "title": "💻 Online"},
            {"id": "b2_mode_offline", "title": "🏫 Offline"},
            {"id": "b2_mode_hybrid",  "title": "🔀 Hybrid"},
        ],
    )


# ---------------------------------------------------------------------------
# Bot 2 — Main text handler
# ---------------------------------------------------------------------------

def b2_handle_text(sender, text, session):
    state = session.get('state', 'initial')

    if state == 'b2_awaiting_name':
        name = text.strip().title()
        if len(name) < 2:
            b2_send_text(sender, "Please enter your full name. 😊")
            return
        session['name']  = name
        session['state'] = 'b2_awaiting_location'
        sessions2[sender] = session
        b2_send_text(sender, "Great! 📍 Could you share your *location* (city/state)?")

    elif state == 'b2_awaiting_location':
        session['location'] = text.strip().title()
        session['state']    = 'b2_awaiting_qualification'
        sessions2[sender]   = session
        b2_send_text(sender, "Thanks! 🎓 What is your *highest qualification*?")

    elif state == 'b2_awaiting_qualification':
        session['qualification'] = text.strip()
        session['state']         = 'b2_done'
        sessions2[sender]        = session
        # Save with enriched note
        interest = session.get('interest', 'IMTTC courses')
        note     = (f"Location: {session.get('location','N/A')} | "
                    f"Qualification: {session.get('qualification','N/A')} | "
                    f"Interest: {interest}")
        save_lead(session.get('name', 'Unknown'), sender, interest, note, COMPANY_ID_2)
        session['lead_saved'] = True
        sessions2[sender]     = session
        b2_ask_qualifier(sender)

    else:
        sessions2[sender] = {'state': 'initial'}
        b2_send_welcome(sender)


# ---------------------------------------------------------------------------
# Bot 2 — Main button/list handler
# ---------------------------------------------------------------------------

def b2_handle_button_or_list(sender, item_id, session):

    # Main menu
    if item_id == 'b2_courses':
        session['state'] = 'b2_browsing'
        sessions2[sender] = session
        b2_send_course_menu(sender)
        return

    if item_id == 'b2_admission':
        b2_send_admission(sender)
        return

    if item_id == 'b2_fees':
        b2_send_fees(sender)
        return

    if item_id == 'b2_career':
        b2_send_career(sender)
        return

    if item_id == 'b2_counsellor':
        interest = session.get('interest', 'IMTTC courses')
        session['state']    = 'b2_awaiting_name'
        session['interest'] = interest
        sessions2[sender]   = session
        b2_ask_call_time(sender)
        return

    if item_id == 'b2_end_chat':
        sessions2[sender] = {'state': 'initial'}
        b2_send_text(
            sender,
            "Thank you for reaching out to *IMTTC*! 🎓\n\n"
            "We wish you all the best in your teaching journey. Feel free to message us anytime. 😊"
        )
        return

    # Course detail
    if item_id.startswith('b2_course_'):
        b2_send_course_detail(sender, item_id, session)
        return

    # Syllabus (placeholder — update with actual syllabus content)
    if item_id.startswith('b2_syllabus|'):
        course_id   = item_id.split('|', 1)[1]
        course_name = course_id.replace('b2_course_', '').upper()
        b2_send_text(
            sender,
            f"📋 *Syllabus – {course_name}*\n\n"
            "Our curriculum covers:\n"
            "• Montessori philosophy & principles\n"
            "• Child development & psychology\n"
            "• Classroom management\n"
            "• Practical teaching sessions\n"
            "• Assessment & documentation\n\n"
            "For the full detailed syllabus, speak with our counsellor!"
        )
        b2_send_buttons(sender, "Would you like to talk to a counsellor?",
            [
                {"id": "b2_counsellor", "title": "🎓 Talk to Counselor"},
                {"id": "b2_courses",    "title": "📚 Other Courses"},
                {"id": "b2_fees",       "title": "💰 Fees & Duration"},
            ])
        return

    # Career scope
    if item_id.startswith('b2_career_scope|'):
        b2_send_career(sender)
        return

    # Fees sub-options
    if item_id == 'b2_fees_exact':
        b2_send_text(
            sender,
            "💲 *Exact Fee Details*\n\n"
            "Fees depend on the course and mode of study:\n\n"
            "• Certificate / Short-term: From ₹12,000\n"
            "• Diploma programmes: ₹20,000 – ₹50,000\n"
            "• PG / Master level: Up to ₹85,000\n\n"
            "Contact our counsellor for the exact fee for your chosen course."
        )
        b2_send_buttons(sender, "Would you like to speak with a counsellor?",
            [
                {"id": "b2_counsellor", "title": "🎓 Talk to Counselor"},
                {"id": "b2_fees_emi",   "title": "🏦 EMI Options"},
                {"id": "b2_courses",    "title": "📚 View Courses"},
            ])
        return

    if item_id == 'b2_fees_emi':
        b2_send_text(
            sender,
            "🏦 *EMI / Instalment Options*\n\n"
            "Yes! You don't need to pay everything upfront.\n\n"
            "We offer easy, flexible instalment plans with *no hidden charges*.\n\n"
            "All study materials, exams, and certification are included."
        )
        b2_send_buttons(sender, "Want personalised fee guidance?",
            [
                {"id": "b2_counsellor",        "title": "🎓 Talk to Counselor"},
                {"id": "b2_fees_scholarship",  "title": "🎁 Scholarship Info"},
                {"id": "b2_courses",           "title": "📚 View Courses"},
            ])
        return

    if item_id == 'b2_fees_scholarship':
        b2_send_text(
            sender,
            "🎁 *Scholarship Availability*\n\n"
            "We have limited scholarships available for deserving candidates.\n\n"
            "Speak with our counsellor to check your eligibility!"
        )
        b2_send_buttons(sender, "Talk to a counsellor about scholarships?",
            [
                {"id": "b2_counsellor", "title": "🎓 Yes, Talk Now"},
                {"id": "b2_courses",    "title": "📚 View Courses"},
            ])
        return

    # Admission form
    if item_id == 'b2_apply_yes':
        session['state']    = 'b2_awaiting_name'
        session['interest'] = 'Admission Form'
        sessions2[sender]   = session
        b2_prompt_name(sender, 'sending the application form')
        return

    # Placement
    if item_id == 'b2_placement_yes':
        session['state']    = 'b2_awaiting_name'
        session['interest'] = 'Placement Guidance'
        sessions2[sender]   = session
        b2_prompt_name(sender, 'placement guidance')
        return

    # Call time preference
    if item_id in ('b2_time_morning', 'b2_time_afternoon', 'b2_time_evening'):
        time_map = {
            'b2_time_morning':   'Morning',
            'b2_time_afternoon': 'Afternoon',
            'b2_time_evening':   'Evening',
        }
        session['preferred_time'] = time_map[item_id]
        session['state']          = 'b2_awaiting_name'
        sessions2[sender]         = session
        b2_prompt_name(sender)
        return

    # Qualifier — currently working?
    if item_id in ('b2_working_yes', 'b2_working_no'):
        session['currently_working'] = 'Yes' if item_id == 'b2_working_yes' else 'No'
        sessions2[sender] = session
        b2_ask_mode(sender)
        return

    # Mode preference
    if item_id in ('b2_mode_online', 'b2_mode_offline', 'b2_mode_hybrid'):
        mode_map = {
            'b2_mode_online':  'Online',
            'b2_mode_offline': 'Offline',
            'b2_mode_hybrid':  'Hybrid',
        }
        session['preferred_mode'] = mode_map[item_id]
        sessions2[sender]         = session
        b2_confirm_lead(sender, session)
        return

    # Fallback
    sessions2[sender] = {'state': 'initial'}
    b2_send_welcome(sender)


# ---------------------------------------------------------------------------
# Bot 2 — Webhook routes
# ---------------------------------------------------------------------------

@app.route('/webhook2', methods=['GET'])
def verify2():
    mode      = request.args.get('hub.mode')
    token     = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == VERIFY_TOKEN_2:
        print("✅ Bot2 Webhook Verified!")
        return challenge, 200
    return "Verification failed", 403


@app.route('/webhook2', methods=['POST'])
def webhook2():
    data = request.get_json()
    try:
        entry    = data.get('entry', [{}])[0]
        changes  = entry.get('changes', [{}])[0]
        value    = changes.get('value', {})
        messages = value.get('messages', [])

        if not messages:
            return make_response("EVENT_RECEIVED", 200)

        message  = messages[0]
        sender   = message.get('from')
        msg_type = message.get('type')
        msg_id   = message.get('id')
        session  = sessions2.get(sender, {'state': 'initial'})

        if msg_id:
            send_typing_indicator(sender, msg_id, ACCESS_TOKEN_2, PHONE_NUMBER_ID_2)

        print(f"📩 [Bot2/IMTTC] [{msg_type}] from {sender} | state: {session.get('state')}")

        if msg_type == 'text':
            text = message.get('text', {}).get('body', '').strip()
            b2_handle_text(sender, text, session)

        elif msg_type == 'interactive':
            interactive = message.get('interactive', {})
            itype       = interactive.get('type')
            if itype == 'button_reply':
                b2_handle_button_or_list(sender, interactive['button_reply']['id'], session)
            elif itype == 'list_reply':
                b2_handle_button_or_list(sender, interactive['list_reply']['id'], session)

        elif msg_type in ('image', 'document', 'audio', 'video', 'sticker'):
            b2_send_text(
                sender,
                "Thank you for your message! 😊 I can only process text right now.\n\n"
                "Please type *Hi* to get back to the menu."
            )
            sessions2[sender] = {'state': 'initial'}
            b2_send_welcome(sender)

    except Exception as e:
        print(f"❌ Bot2 Webhook Error: {e}")

    return make_response("EVENT_RECEIVED", 200)


# ===========================================================================
# RUN
# ===========================================================================

if __name__ == '__main__':
    app.run(port=5003, debug=True)