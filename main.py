import requests
import re
import json
import time
import os
from datetime import datetime
from threading import Thread

# ============ CONFIGURACIÓN ============
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
NUMERO_PPT = os.environ.get("NUMERO_PPT")

# =======================================

BASE_URL = "https://apps.migracioncolombia.gov.co/aplicaciones"
LIVEWIRE_URL = f"{BASE_URL}/livewire/message/main.entrega-ppt.entrega-ppt-component"

last_update_id = 0


def enviar_telegram(mensaje):
    """Envía mensaje a Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": mensaje, "parse_mode": "HTML"})


def consultar_ppt():
    """Consulta el estado del PPT en Migración Colombia"""
    hora = datetime.now().strftime("%Y-%m-%d %H:%M")

    try:
        session = requests.Session()

        # 1. Obtener página inicial para extraer el estado Livewire
        response = session.get(f"{BASE_URL}/entrega-ppt", timeout=30)
        response.raise_for_status()

        # 2. Extraer el estado inicial de Livewire del HTML
        match = re.search(r'wire:initial-data="([^"]+)"', response.text)
        if not match:
            enviar_telegram(f"⚠️ [{hora}] No se pudo extraer datos Livewire")
            return

        # Decodificar el JSON (viene como HTML entities)
        initial_data = json.loads(match.group(1).replace("&quot;", '"'))

        # 3. Preparar el payload para la búsqueda
        payload = {
            "fingerprint": initial_data["fingerprint"],
            "serverMemo": initial_data["serverMemo"],
            "updates": [
                {
                    "type": "syncInput",
                    "payload": {
                        "id": "rumv-input",
                        "name": "rumv",
                        "value": NUMERO_PPT
                    }
                },
                {
                    "type": "callMethod",
                    "payload": {
                        "id": "buscar-btn",
                        "method": "buscar",
                        "params": []
                    }
                }
            ]
        }

        # 4. Hacer la consulta
        headers = {
            "Content-Type": "application/json",
            "X-Livewire": "true",
            "Referer": f"{BASE_URL}/entrega-ppt"
        }

        response = session.post(LIVEWIRE_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()

        result = response.json()
        data = result.get("serverMemo", {}).get("data", {})

        busqueda = data.get("busqueda", False)
        alerta = data.get("alerta", False)

        # 5. Interpretar resultado
        if busqueda and not alerta:
            mensaje = f"""
🎉🎉🎉 <b>¡TU PPT ESTÁ LISTO!</b> 🎉🎉🎉

📅 Fecha: {hora}
📋 Número: {NUMERO_PPT}

¡Ve a recogerlo a tu Centro Facilitador!
            """
            enviar_telegram(mensaje)
        elif busqueda and alerta:
            enviar_telegram(f"📋 [{hora}] PPT {NUMERO_PPT}: Aún NO está listo para entrega")
        else:
            enviar_telegram(f"⚠️ [{hora}] Respuesta inesperada: busqueda={busqueda}, alerta={alerta}")

    except requests.exceptions.RequestException as e:
        enviar_telegram(f"❌ [{hora}] Error de conexión: {str(e)}")
    except Exception as e:
        enviar_telegram(f"❌ [{hora}] Error: {str(e)}")


def escuchar_comandos():
    """Escucha comandos de Telegram"""
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"

    while True:
        try:
            response = requests.get(url, params={"offset": last_update_id + 1, "timeout": 30})
            updates = response.json().get("result", [])

            for update in updates:
                last_update_id = update["update_id"]
                mensaje = update.get("message", {})
                texto = mensaje.get("text", "")

                if texto == "/consultar":
                    enviar_telegram("🔍 Consultando estado del PPT...")
                    consultar_ppt()
                elif texto == "/status":
                    enviar_telegram(f"✅ Bot activo\n📋 Monitoreando PPT: {NUMERO_PPT}")
                elif texto == "/help":
                    enviar_telegram(
                        "📖 <b>Comandos disponibles:</b>\n\n"
                        "/consultar - Consulta el estado del PPT ahora\n"
                        "/status - Verifica que el bot esté activo\n"
                        "/help - Muestra esta ayuda"
                    )
        except Exception as e:
            print(f"Error escuchando comandos: {e}")
            time.sleep(5)


def consultas_programadas():
    """Ejecuta consultas en horarios específicos"""
    while True:
        ahora = datetime.now()
        hora_actual = ahora.strftime("%H:%M")

        if hora_actual in ["08:00", "16:00"]:
            consultar_ppt()
            time.sleep(60)  # Evitar doble ejecución

        time.sleep(30)


def main():
    print(f"🤖 Bot iniciado - Monitoreando PPT: {NUMERO_PPT}")
    print(f"🕐 Hora actual del servidor: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Version 2.0")
    enviar_telegram(f"🤖 Bot iniciado!\n📋 Monitoreando PPT: {NUMERO_PPT}\n\nUsa /help para ver comandos")

    # Hilo para escuchar comandos
    Thread(target=escuchar_comandos, daemon=True).start()

    # Hilo para consultas programadas
    consultas_programadas()


if __name__ == "__main__":
    main()
