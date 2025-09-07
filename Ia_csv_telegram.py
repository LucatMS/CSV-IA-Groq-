import os
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from groq import Groq  # pip install groq


# ==== CREDENCIAIS  ====

# GROQ
GROQ_API_KEY = "API GROQ"  # <- YOUR API KEY
GROQ_MODEL = "llama-3.3-70b-versatile"

# TELEGRAM (Bot API via HTTP)
TELEGRAM_BOT_TOKEN = "TOKEN"  # <- BOT TOKEN
TELEGRAM_CHAT_ID = " CHAT ID"  # <- CHAT ID

# (Opcional) Caso use Telethon no futuro (NÃO usado aqui):
TELEGRAM_API_ID = "ID AQUI"
TELEGRAM_API_HASH = "API HASH"
# =========================================================

# --- Caminho do CSV ---
csv_path = r"C:\Users\Usuario..." # DIRECTORY .CSV AQUI , SAME FOLDER OF SCRIPT

# --- Prompt-base para a IA  ---
PROMPT_BASE = """Você é uma assistente de copy para WhatsApp/Telegram. 
Escreva UMA mensagem curta, calorosa e personalizada de {tipo} para {nome}.
Regras:
- Tom: humano, carinhoso e positivo (sem soar robótico).
- 2 a 4 frases, no máximo 420 caracteres.
- Use 2 ou 3 emojis relevantes (sem exagero).
- Coloque um titulo de Feliz aniversario separado da mensagem faça um paragrafo e depois joga a mensagem
- Não use {nome} mais de uma vez.
- Não peça para responder; evite clichês genéricos.
- Se {tipo} for "aniversário", inclua um desejo de saúde e conquistas no novo ciclo.
- Se {tipo} for uma data comemorativa, cite a data (“{tipo}”) de forma natural.
- Deixe mais dinamido a mensagem e bonita, gere espaçamentos entre a mensagem de aniversario e o cupom.
- Adicione um cupom de desconto Utilize esse nosso cupom:"ANIVERSARIO10" no final da mensagem para a pessoa usar em suas compras como presente 
Produza apenas o texto final, sem cabeçalho nem aspas. 
"""

# --- Datas comemorativas (DD/MM: rótulo) ---
special_dates = {
    "25/12": "Natal 🎄",
    "01/01": "Ano Novo 🎆",
    "12/06": "Dia dos Namorados ❤️",  # Brasil
    # adicione outras datas conforme necessário
}

# ---------- Funções auxiliares ----------
def parse_data_excel_ou_texto(valor):
    """Converte serial do Excel ou string (YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY) em datetime.
       Retorna None se não conseguir."""
    if pd.isna(valor):
        return None

    # número serial do Excel
    if isinstance(valor, (int, float)):
        try:
            excel_epoch = datetime(1899, 12, 30)
            return excel_epoch + timedelta(days=int(valor))
        except Exception:
            return None

    # strings em formatos comuns
    if isinstance(valor, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(valor.strip(), fmt)
            except ValueError:
                continue
    return None

def gerar_mensagem_groq(client: Groq, nome: str, tipo: str) -> str:
    """Gera copy com Groq. Se falhar, retorna um fallback simples."""
    try:
        prompt = PROMPT_BASE.format(nome=nome, tipo=tipo)
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            temperature=0.85,
            max_tokens=220,
            messages=[
                {"role": "system", "content": "Você escreve mensagens curtas e humanas para WhatsApp/Telegram."},
                {"role": "user", "content": prompt},
            ],
        )
        texto = resp.choices[0].message.content.strip()
        # Sanitização simples
        return " ".join(texto.split())
    except Exception:
        if tipo == "aniversário":
            return f"Feliz aniversário, {nome}! 🎉 Que seu novo ciclo traga saúde, paz e muitas conquistas."
        else:
            return f"{tipo} feliz, {nome}! Que seu dia seja especial. ✨"

# ---------- Envio Telegram via HTTP ----------
def telegram_send_message(bot_token: str, chat_id: str, text: str) -> bool:
    try:
        # Segurança com limite Telegram (4096 chars):
        if len(text) > 4096:
            text = text[:4093] + "..."

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        r = requests.post(url, data=payload, timeout=10)
        data = r.json()
        if not data.get("ok"):
            print(f"[ERRO Telegram] {json.dumps(data, ensure_ascii=False)}")
        return data.get("ok", False)
    except Exception as e:
        print(f"[ERRO Telegram] {e}")
        return False

def telegram_get_updates(bot_token: str):
    """Útil para conferir se o bot recebeu /start e para descobrir chat_id."""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        r = requests.get(url, timeout=10)
        data = r.json()
        print("[DEBUG getUpdates] resposta bruta:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"[ERRO getUpdates] {e}")

# ---------- Fluxo principal ----------
def main():
    # 2) Ler CSV e manter colunas essenciais
    df = pd.read_csv(csv_path)
    columns_needed = ["nome", "telefone", "data_nascimento"]
    df = df[[col for col in columns_needed if col in df.columns]]

    # 3) Data de hoje (DD/MM)
    hoje = datetime.now()
    today_str = hoje.strftime("%d/%m")
    print(f"\nData de hoje: {today_str}\n")

    # 4) Inicializar cliente Groq
    client = Groq(api_key=GROQ_API_KEY)

    # 5) Construir lista de destinatários
    destinos = []  # cada item: {nome, telefone, motivo}

    # Caso 1: aniversários hoje
    for _, row in df.iterrows():
        nome = str(row.get("nome", "")).strip()
        telefone = str(row.get("telefone", "")).strip()
        data_nasc = row.get("data_nascimento")

        if not nome or not telefone:
            continue

        birth_date = parse_data_excel_ou_texto(data_nasc)
        if birth_date is None:
            continue

        if birth_date.strftime("%d/%m") == today_str:
            destinos.append({"nome": nome, "telefone": telefone, "motivo": "aniversário"})

    # Caso 2: datas comemorativas (envia para todos da planilha)
    if today_str in special_dates:
        etiqueta = special_dates[today_str]
        for _, row in df.iterrows():
            nome = str(row.get("nome", "")).strip()
            telefone = str(row.get("telefone", "")).strip()
            if nome and telefone:
                destinos.append({"nome": nome, "telefone": telefone, "motivo": etiqueta})

    # 6) Geração + envio
    if not destinos:
        print("Nenhum aniversariante ou data comemorativa hoje.")
        return

    print("Enviando mensagens de campanha:\n")
    enviados = 0
    falhas = 0

    for d in destinos:
        nome = d["nome"]
        motivo = d["motivo"]
        mensagem = gerar_mensagem_groq(client, nome, motivo)

        ok = telegram_send_message(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, mensagem)
        if ok:
            enviados += 1
            print(f"✅ Enviado para: {nome} | Motivo: {motivo}")
        else:
            falhas += 1
            print(f"❌ Falha ao enviar para: {nome} | Motivo: {motivo}")

    print(f"\nResumo: {enviados} enviados | {falhas} falhas")

if __name__ == "__main__":
    main()
