import os
import stripe
from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Carrega as variáveis (útil para teste local, no Render ele usa as Environment Variables)
load_dotenv()

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Conexão com o MongoDB
mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client.auction_bot  # Certifique-se que o nome do banco é o mesmo do bot

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        # Verifica se o sinal vem mesmo do Stripe
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except Exception as e:
        print(f"⚠️ Erro na assinatura do Webhook: {e}")
        return jsonify(success=False), 400

    # Quando o pagamento é concluído com sucesso
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # Coleta os dados usando getattr para evitar o erro de 'StripeObject'
        guild_id = getattr(session, 'client_reference_id', None)
        amount_paid = getattr(session, 'amount_total', 0)

        print(f"💳 Pagamento detectado! Guild: {guild_id} | Valor: {amount_paid} centavos")

        # Define os dias de assinatura com base no valor pago
        dias = 30
        if amount_paid >= 12499:   # R$ 124,99
            dias = 365
        elif amount_paid >= 5999:  # R$ 59,99
            dias = 180

        if guild_id:
            expiry = datetime.now() + timedelta(days=dias)
            try:
                # Grava a ativação no MongoDB
                db.guilds.update_one(
                    {"guild_id": str(guild_id)},
                    {"$set": {
                        "status": "active",
                        "expires_at": expiry.isoformat(),
                        "last_payment": datetime.now(),
                        "plano_dias": dias
                    }},
                    upsert=True
                )
                print(f"✅ Sucesso! Servidor {guild_id} ativado por {dias} dias no banco de dados.")
            except Exception as e:
                print(f"❌ Erro crítico ao salvar no MongoDB: {e}")
        else:
            print("⚠️ Erro: client_reference_id não encontrado na sessão do Stripe.")

    return jsonify(success=True)

if __name__ == '__main__':
    # O Render define a porta automaticamente na variável de ambiente PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
