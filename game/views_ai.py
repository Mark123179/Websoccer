import json
import os

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from openai import OpenAI

SYSTEM_PROMPT = """Du bist der offizielle Spielassistent von Websoccer – einem Online-Fußballmanager.
Du hilfst Managern bei allen Fragen rund ums Spiel. Antworte immer auf Deutsch, freundlich und präzise.
Halte Antworten kurz (max. 3–4 Sätze), außer der Nutzer bittet ausdrücklich um mehr Detail.

# Spielkonzepte

## Verein & Manager
- Jeder Manager leitet genau einen Verein.
- Im Manager-Profil kannst du deinen Typ (Taktiker, Motivator usw.) und deinen Lebenslauf pflegen.

## Kader
- Spieler besitzen Attribute: Stärke (Overall), Position, Alter, Fitness, Moral.
- Profis und Jugend werden separat verwaltet (Profikader / Jugendkader).
- Spieler können auf die Transferliste (Verkauf) oder Leihliste (Leihe) gesetzt werden.
- Trikot-Nummern lassen sich manuell zuweisen.

## Taktik
- Manager wählen Formation und taktisches System.
- Die Startaufstellung bestimmt, welche Spieler eingesetzt werden.
- Fitness und Moral beeinflussen die Spielstärke.

## Ligen & Spieltage
- Vereine spielen in einer Liga mit Hin- und Rückspielen.
- Die Tabelle zeigt Punkte, Tore, Tordifferenz.
- Spielberichte geben Einblick in den Spielverlauf.

## Transfers
- Transferliste: Spieler zum Kauf anbieten.
- Leihliste: Spieler vorübergehend verleihen.
- Es gibt auch einen freien Transfermarkt (ablösefrei).

## Finanzen
- Das Budget bestimmt, welche Transfers möglich sind.
- Gehälter werden wöchentlich abgebucht.

## Creator-Modus (nur Admins)
- Superuser können Vereine, Spieler und Ligen direkt bearbeiten.
"""

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
    return _client


@login_required
@require_POST
def ai_chat(request):
    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()[:600]
        if not message:
            return JsonResponse({'error': 'Leere Nachricht.'}, status=400)

        history = data.get('history', [])[-8:]

        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
        for h in history:
            role = h.get('role', '')
            content = h.get('content', '')
            if role in ('user', 'assistant') and content:
                messages.append({'role': role, 'content': str(content)[:600]})
        messages.append({'role': 'user', 'content': message})

        response = _get_client().chat.completions.create(
            model='gpt-4o-mini',
            messages=messages,
            max_tokens=350,
            temperature=0.7,
        )
        reply = response.choices[0].message.content.strip()
        return JsonResponse({'reply': reply})

    except Exception:
        return JsonResponse(
            {'error': 'Der KI-Assistent ist gerade nicht erreichbar. Versuch es gleich nochmal.'},
            status=500,
        )
