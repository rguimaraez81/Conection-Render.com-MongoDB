import os
import stripe
from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configurações
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client.auction_bot 

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except Exception as e:
        return jsonify(success=False, error=str(e)), 400

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        guild_id = session.get('client_reference_id')
        amount_paid = session.get('amount_total', 0)

        # Regra de dias (as mesmas que definimos ontem)
        dias = 30
        if amount_paid >= 12499: dias = 365
        elif amount_paid >= 5999: dias = 180

        if guild_id:
            expiry = datetime.now() + timedelta(days=dias)
            # Atualiza o MongoDB diretamente
            db.guilds.update_one(
                {"guild_id": str(guild_id)},
                {"$set": {
                    "status": "active",
                    "expires_at": expiry.isoformat(),
                    "last_payment": datetime.now()
                }},
                upsert=True
            )
            print(f"✅ Servidor {guild_id} ativado via Render!")

    return jsonify(success=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
