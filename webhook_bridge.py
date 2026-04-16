import os
import stripe
from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Carrega as variáveis (para ambiente local)
load_dotenv()

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

# Conexão com o MongoDB
# O nome do banco de dados deve ser 'auction_bot' para bater com o código anterior
mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client.auction_bot 

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        # Verifica a autenticidade do sinal do Stripe
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
    except Exception as e:
        print(f"⚠️ Erro na assinatura do Webhook: {e}")
        return jsonify(success=False), 400

    # Evento disparado quando o checkout é concluído com sucesso
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # --- CORREÇÃO PARA EVITAR ATTRIBUTE ERROR ---
        guild_id = getattr(session, 'client_reference_id', None)
        amount_paid = getattr(session, 'amount_total', 0)

        print(f"💳 Pagamento recebido! Guild: {guild_id} | Valor: {amount_paid} centavos")

        # Regra de dias baseada nos seus valores reais
        dias = 30
        if amount_paid >= 12499:   # R$ 124,99 (Anual)
            dias = 365
        elif amount_paid >= 5999:  # R$ 59,99 (Semestral)
            dias = 180

        if guild_id:
            expiry = datetime.now() + timedelta(days=dias)
            try:
                # Atualiza ou cria a assinatura na coleção 'guilds'
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
                print(f"✅ Sucesso! Servidor {guild_id} ativado por {dias} dias.")
            except Exception as e:
                print(f"❌ Erro ao salvar no MongoDB: {e}")
        else:
            print("⚠️ Erro: client_reference_id não encontrado na sessão.")

    return jsonify(success=True)

if __name__ == '__main__':
    # Render usa a porta 10000 por padrão
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
