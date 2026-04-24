const express = require('express');
const axios = require('axios');
require('dotenv').config();

const app = express();
app.use(express.json());

const { PORT, ACCESS_TOKEN, PHONE_NUMBER_ID, VERIFY_TOKEN } = process.env;

// 1. Webhook Verification for Meta
app.get('/webhook', (req, res) => {
    const mode = req.query['hub.mode'];
    const token = req.query['hub.verify_token'];
    const challenge = req.query['hub.challenge'];

    if (mode === 'subscribe' && token === VERIFY_TOKEN) {
        console.log("✅ Webhook Verified Successfully!");
        return res.status(200).send(challenge);
    }
    res.sendStatus(403);
});

// 2. Receiving and Responding to Messages
app.post('/webhook', async (req, res) => {
    const incoming = req.body.entry?.[0]?.changes?.[0]?.value?.messages?.[0];

    if (incoming) {
        const from = incoming.from; // Sender's ID
        const text = incoming.text?.body; // Message content
        const msgId = incoming.id; // Message ID for typing indicator

        console.log(`📩 Received: "${text}" from ${from}`);

        // Show typing animation
        if (msgId) {
            await sendTypingIndicator(from, msgId);
        }

        // Simple Echo logic
        await sendWhatsAppMessage(from, `Bot received: ${text}`);
    }
    res.sendStatus(200);
});

async function sendTypingIndicator(to, msgId) {
    try {
        await axios({
            method: 'POST',
            url: `https://graph.facebook.com/v21.0/${PHONE_NUMBER_ID}/messages`,
            data: {
                messaging_product: "whatsapp",
                status: "read",
                message_id: msgId,
                typing_indicator: {
                    type: "text"
                }
            },
            headers: { "Authorization": `Bearer ${ACCESS_TOKEN}` }
        });
    } catch (err) {
        console.error("❌ Typing Indicator Error:", err.response?.data || err.message);
    }
}

async function sendWhatsAppMessage(to, message) {
    try {
        await axios({
            method: 'POST',
            url: `https://graph.facebook.com/v21.0/${PHONE_NUMBER_ID}/messages`,
            data: {
                messaging_product: "whatsapp",
                to: to,
                text: { body: message }
            },
            headers: { "Authorization": `Bearer ${ACCESS_TOKEN}` }
        });
    } catch (err) {
        console.error("❌ Send Error:", err.response?.data || err.message);
    }
}

app.listen(PORT, () => console.log(`🚀 Server running on port ${PORT}`));