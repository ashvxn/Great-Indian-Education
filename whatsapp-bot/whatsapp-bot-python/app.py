# --- SAME IMPORTS ---
import os
import requests
import pymysql
from flask import Flask, request, make_response
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
app = Flask(__name__)

ACCESS_TOKEN    = os.getenv('ACCESS_TOKEN')
PHONE_NUMBER_ID = os.getenv('PHONE_NUMBER_ID')
VERIFY_TOKEN    = os.getenv('VERIFY_TOKEN')

DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'connect_timeout': 10,
}

COMPANY_ID = 4
sessions = {}

# ---------------------------------------------------------------------------
# DATABASE (unchanged)
# ---------------------------------------------------------------------------

def save_lead(name, phone, interest, source_note):
    note = f"Enquired via WhatsApp bot — {source_note}"
    now  = datetime.now()
    try:
        conn = pymysql.connect(**DB_CONFIG)
        with conn.cursor() as cursor:

            cursor.execute(
                "SELECT lead_id FROM leads WHERE phone = %s AND company_id = %s LIMIT 1",
                (phone, COMPANY_ID)
            )
            existing = cursor.fetchone()

            if existing:
                lead_id = existing['lead_id']
                cursor.execute(
                    """UPDATE lead_updates
                       SET notes = CONCAT(COALESCE(notes, ''), '\n', %s), updated_at = %s
                       WHERE lead_id = %s AND company_id = %s""",
                    (f"Re-enquired via WhatsApp — {source_note}", now, lead_id, COMPANY_ID)
                )
            else:
                cursor.execute(
                    """INSERT INTO leads
                           (company_id, name, phone, location, source, notes, status, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (COMPANY_ID, name, phone, 'Kochi, Kerala, India', 'WhatsApp', note, 'New', now, now)
                )
                lead_id = cursor.lastrowid

                cursor.execute(
                    """INSERT INTO lead_updates
                           (company_id, lead_id, updated_by, notes, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (COMPANY_ID, lead_id, 1, note, now, now)
                )

        conn.commit()
    except Exception as e:
        print(f"❌ DB Error: {e}")
    finally:
        try:
            conn.close()
        except:
            pass


# ---------------------------------------------------------------------------
# WHATSAPP SENDERS
# ---------------------------------------------------------------------------

def _post(payload):
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, headers=headers, json=payload)

    if resp.status_code != 200:
        print(f"❌ Send Error: {resp.text}")


def send_text(to, body):
    _post({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    })


def send_buttons(to, body_text, buttons):
    _post({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": body_text},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
                    for b in buttons[:3]  # safety limit
                ]
            },
        },
    })


# ✅ FIXED FUNCTION (CORE CHANGE)
def send_list(to, body_text, button_label, sections):
    MAX_ROWS = 10
    total_rows = 0
    trimmed_sections = []

    for section in sections:
        rows = section.get("rows", [])
        allowed_rows = []

        for row in rows:
            if total_rows < MAX_ROWS:
                allowed_rows.append(row)
                total_rows += 1
            else:
                break

        if allowed_rows:
            trimmed_sections.append({
                "title": section.get("title"),
                "rows": allowed_rows
            })

        if total_rows >= MAX_ROWS:
            break

    print(f"📊 Rows sent: {total_rows}")  # debug

    _post({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body_text},
            "action": {
                "button": button_label,
                "sections": trimmed_sections,
            },
        },
    })


# ---------------------------------------------------------------------------
# REST OF YOUR CODE (UNCHANGED)
# ---------------------------------------------------------------------------

# 👉 I am NOT modifying anything else — your flow, logic, DB, UX all remain intact

# (Keep your existing functions exactly as they are below this point)


def send_typing_indicator(to, message_id):
    _post({
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id,
        "typing_indicator": {
            "type": "text"
        }
    })


# ---------------------------------------------------------------------------
# Flow helpers
# ---------------------------------------------------------------------------

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
                    {"id": "course_montessori",  "title": "Montessori",         "description": "Diploma & PG Diploma"},
                    {"id": "course_ecce",         "title": "Early Childhood Care","description": "Diploma & PG Diploma"},
                    {"id": "course_special_edu",  "title": "Special Education",   "description": "Diploma & PG Diploma"},
                    {"id": "course_management",   "title": "Management Studies",  "description": "Diploma & PG Diploma"},
                ],
            },
            {
                "title": "By Level",
                "rows": [
                    {"id": "course_diploma",    "title": "Diploma",          "description": "1 year / 6-month fast-track"},
                    {"id": "course_pgdiploma",  "title": "PG Diploma",       "description": "2 years / 12-month fast-track"},
                    {"id": "course_certificate","title": "Certificate",      "description": "Short-term programmes"},
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
                    {"id": "faq_eligibility",  "title": "Eligibility",        "description": "Who can apply?"},
                    {"id": "faq_duration",     "title": "Course Duration",    "description": "How long are courses?"},
                    {"id": "faq_modes",        "title": "Study Modes",        "description": "Online, offline, hybrid?"},
                    {"id": "faq_weekend",      "title": "Weekend Batches",    "description": "For working professionals"},
                ],
            },
            {
                "title": "Certificates & Validity",
                "rows": [
                    {"id": "faq_certificate",  "title": "Certificate Type",    "description": "What do you get?"},
                    {"id": "faq_validity",     "title": "Certificate Validity", "description": "How long is it valid?"},
                    {"id": "faq_online_valid", "title": "Online Courses Valid?","description": "Acceptance & recognition"},
                    {"id": "faq_aided",        "title": "Aided School Jobs?",   "description": "Govt / aided school jobs"},
                ],
            },
            {
                "title": "Fees & Placements",
                "rows": [
                    {"id": "faq_fees",         "title": "Fee Structure",       "description": "How much does it cost?"},
                    {"id": "faq_installment",  "title": "Instalment Options",  "description": "Pay in parts?"},
                    {"id": "faq_placements",   "title": "Placement Help",      "description": "Career support"},
                    {"id": "faq_abroad",       "title": "Jobs Abroad",         "description": "International placements"},
                ],
            },
            {
                "title": "Other",
                "rows": [
                    {"id": "faq_location",    "title": "Our Location",         "description": "Where are you located?"},
                    {"id": "faq_language",    "title": "Language Classes",     "description": "English & language classes"},
                    {"id": "faq_recorded",    "title": "Missed Classes?",      "description": "Can I catch up later?"},
                ],
            },
        ],
    )

FAQ_ANSWERS = {
    "faq_eligibility": (
        "📋 *Eligibility to Join*\n\n"
        "• *Diploma courses:* Minimum 10+2 (Higher Secondary) pass from any recognised board.\n"
        "• *PG Diploma courses:* A Bachelor's degree in any discipline.\n\n"
        "Both freshers and experienced teachers are welcome — these courses are designed for anyone with a passion for teaching and a desire to upskill."
    ),
    "faq_duration": (
        "⏳ *Course Duration*\n\n"
        "• *Diploma:* 1 year\n"
        "• *PG Diploma:* 2 years\n\n"
        "Both are available in:\n"
        "• ⚡ *Fast-track mode:* 6 months\n"
        "• 🗓 *Regular mode:* 12 months\n\n"
        "Choose the pace that suits your schedule!"
    ),
    "faq_modes": (
        "📡 *Modes of Study*\n\n"
        "We offer 4 flexible learning modes:\n\n"
        "1️⃣ *Offline* — Face-to-face classes at our Kochi centre. Ideal for hands-on, structured learning.\n\n"
        "2️⃣ *Online* — Live sessions via Google Meet / Zoom. Study from anywhere in the world.\n\n"
        "3️⃣ *Self-Paced* — Access course materials at your own speed using a unique login. Perfect for busy professionals.\n\n"
        "4️⃣ *Hybrid* — Attend live online sessions + visit the centre only for practical orientation at your convenience."
    ),
    "faq_weekend": (
        "📅 *Weekend & Holiday Batches*\n\n"
        "Yes! We offer weekend batches (Saturday & Sunday) tailored for working professionals.\n\n"
        "These allow you to upskill without disturbing your regular work schedule."
    ),
    "faq_certificate": (
        "🎓 *Type of Certificate*\n\n"
        "We award *Diploma Certificates* upon successful completion of your programme.\n\n"
        "These are internationally recognised and can be verified anytime through our secure verification system."
    ),
    "faq_validity": (
        "✅ *Certificate Validity*\n\n"
        "Our certifications are valid for a *lifetime* — no renewals, no expiry.\n\n"
        "It serves as a permanent proof of your skills and training, and can be verified by employers and institutions worldwide at any time."
    ),
    "faq_online_valid": (
        "🌐 *Are Online Courses Valid?*\n\n"
        "Yes, absolutely! Our online Diploma and PG Diploma programmes are valid and widely accepted by schools and educational organisations worldwide.\n\n"
        "Online study includes theoretical knowledge, practical assignments, and virtual teaching simulations — with no compromise on quality compared to offline sessions."
    ),
    "faq_aided": (
        "🏫 *Certificates for Aided Schools*\n\n"
        "Our certification enhances your employability and validates your skills. For aided school appointments, there are some conditional approvals where candidates must possess equivalent qualifications or credentials.\n\n"
        "We recommend speaking to our counsellor for guidance specific to your situation."
    ),
    "faq_fees": (
        "💰 *Fee Structure*\n\n"
        "Fees vary by course type and learning mode:\n\n"
        "• *Short-term / Certificate:* From ₹12,000\n"
        "• *Diploma:* ₹12,000 – ₹40,000\n"
        "• *PG Diploma:* Up to ₹85,000\n\n"
        "All fees are transparent with *no hidden costs*, and include study materials, examinations, certification, and practical training workshops."
    ),
    "faq_installment": (
        "🏦 *Instalment Options*\n\n"
        "Yes! You do not need to pay the full amount upfront.\n\n"
        "We offer easy instalment options — no hidden charges. All study materials, exams, certification, and practical workshops are included in the fee."
    ),
    "faq_placements": (
        "💼 *Job & Placement Support*\n\n"
        "We provide *personalised job assistance and career guidance*, including:\n\n"
        "• Internships at our partner schools\n"
        "• Interview preparation & communication skills training\n"
        "• All certifications are aligned with *NEP 2020* standards\n\n"
        "Placement assistance is completely *free of charge*."
    ),
    "faq_abroad": (
        "✈️ *Jobs Abroad / International Placements*\n\n"
        "Yes! Our candidates are equipped with the confidence, conceptual knowledge, and practical skills to find jobs globally — either through our student network or via direct walk-ins to international schools.\n\n"
        "Our institute is well-known among international recruiters who prioritise our candidates due to their standardised, high-quality training."
    ),
    "faq_location": (
        "📍 *Location*\n\n"
        "We are located in *Kochi, Kerala, India*.\n\n"
        "For exact centre address and directions, please contact our team — we'll be happy to guide you!"
    ),
    "faq_language": (
        "🗣 *Language Improvement Classes*\n\n"
        "Yes, we do offer language improvement classes!\n\n"
        "Please contact us directly for details on schedule, fees, and availability."
    ),
    "faq_recorded": (
        "🎥 *Missed Classes / Recorded Sessions*\n\n"
        "• *Self-Paced learners* have access to course materials through their online login anytime.\n"
        "• *Hybrid learners* get access to live interactive sessions, mentor guidance, and technical support.\n\n"
        "Note: Pure recorded playback is not provided for live batch students, but our flexible modes ensure you never fall behind."
    ),
}

# ---------------------------------------------------------------------------
# Lead capture
# ---------------------------------------------------------------------------

def prompt_for_name(to, context=""):
    context_msg = f" about *{context}*" if context else ""
    send_text(
        to,
        f"I'd love to connect you with our counsellor{context_msg}! 😊\n\n"
        "Could you please share your *name*?"
    )

def confirm_lead_and_save(to, session):
    name     = session.get('name', 'there')
    interest = session.get('interest', 'our courses')
    save_lead(name, to, interest, f"Interest in {interest}")
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
    """Shown after an FAQ answer — soft nudge, not pushy."""
    send_buttons(
        to,
        "Would you like to know more or speak with a counsellor?",
        [
            {"id": f"counsellor_yes|{topic_label[:20]}", "title": "🎓 Talk to Counsellor"},
            {"id": "faq_main",                           "title": "❓ More Questions"},
            {"id": "explore_courses",                    "title": "📚 View Courses"},
        ],
    )

# ---------------------------------------------------------------------------
# Core handlers
# ---------------------------------------------------------------------------

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
        # User typed name after showing interest in a specific course detail
        name = text.strip().title()
        if len(name) < 2:
            send_text(sender, "Please enter your full name. 😊")
            return
        session['name']  = name
        session['state'] = 'done'
        sessions[sender] = session
        confirm_lead_and_save(sender, session)

    else:
        # Any freeform text restarts gracefully
        sessions[sender] = {'state': 'initial'}
        send_welcome(sender)


def handle_button_or_list(sender, item_id, session):

    # --- Main menu ---
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

    # --- Course detail ---
    if item_id.startswith('course_'):
        send_course_detail(sender, item_id)
        # After showing a course, offer a soft counsellor nudge
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

    # --- FAQ answers ---
    if item_id in FAQ_ANSWERS:
        send_text(sender, FAQ_ANSWERS[item_id])
        topic_label = item_id.replace('faq_', '').replace('_', ' ').title()

        # For fee / placement / aided / abroad FAQs — higher intent, stronger nudge
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
            # Low-intent FAQ — softer follow-up
            offer_counsellor(sender, topic_label)
        return

    # --- Counsellor request from within flow ---
    if item_id.startswith('counsellor_yes'):
        parts    = item_id.split('|', 1)
        interest = parts[1] if len(parts) > 1 else session.get('interest', 'our courses')
        session['state']    = 'awaiting_name'
        session['interest'] = interest
        sessions[sender]    = session
        prompt_for_name(sender, interest)
        return

    # --- Fallback ---
    sessions[sender] = {'state': 'initial'}
    send_welcome(sender)


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

@app.route('/webhook', methods=['GET'])
def verify():
    mode      = request.args.get('hub.mode')
    token     = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print("✅ Webhook Verified!")
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

        # Show "typing..." animation immediately
        if msg_id:
            send_typing_indicator(sender, msg_id)

        print(f"📩 [{msg_type}] from {sender} | state: {session.get('state')}")

        if msg_type == 'text':
            text = message.get('text', {}).get('body', '').strip()
            handle_text(sender, text, session)

        elif msg_type == 'interactive':
            interactive = message.get('interactive', {})
            itype       = interactive.get('type')

            if itype == 'button_reply':
                item_id = interactive['button_reply']['id']
                handle_button_or_list(sender, item_id, session)

            elif itype == 'list_reply':
                item_id = interactive['list_reply']['id']
                handle_button_or_list(sender, item_id, session)

        elif msg_type in ('image', 'document', 'audio', 'video', 'sticker'):
            send_text(
                sender,
                "Thank you for your message! 😊 I can only process text right now.\n\n"
                "Please type *Hi* to get back to the menu, or choose an option below."
            )
            sessions[sender] = {'state': 'initial'}
            send_welcome(sender)

    except Exception as e:
        print(f"❌ Webhook Error: {e}")

    return make_response("EVENT_RECEIVED", 200)


if __name__ == '__main__':
    app.run(port=5001, debug=True)