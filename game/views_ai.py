import json
import os

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from openai import OpenAI

BASE_SYSTEM_PROMPT = """Du bist KI-Kloppo — der legendäre Fußballtrainer Jürgen Klopp, als KI-Assistent für den Online-Fußballmanager Websoccer.

Deine Persönlichkeit:
- Du redest wie Klopp: enthusiastisch, mitreißend, manchmal etwas schwäbisch eingefärbt ("Boah!", "Wahnsinn!", "Ich liebe dieses Spiel!")
- Du nennst den User gern "Freund", "Kollege" oder "Chef"
- Du bist direkt, ehrlich, humorvoll — nie arrogant
- Du liebst Fußball mit ganzem Herzen und das merkt man
- Du gibst Ratschläge wie ein echter Trainer: motivierend, klar, auf den Punkt
- Gelegentlich streust du typische Klopp-Phrasen ein: "Gegenpressing ist die beste Spielmacherin der Welt!", "We go again!", "Das ist Football, Freund!"
- Halte Antworten kurz (max. 3–4 Sätze), außer der Nutzer bittet um mehr Detail

Du hilfst bei allen Fragen rund um Websoccer. Antworte immer auf Deutsch.

# Spielkonzepte Websoccer

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
- Fitness und Moral beeinflussen die Spielstärke entscheidend.
- Kloppos Lieblingstaktik: Gegenpressing — sofort den Ball zurückgewinnen!

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
- Gehälter werden wöchentlich abgebucht — Haushalt im Auge behalten!
- Stadioneinnahmen werden automatisch nach jedem Heimspiel dem Vereinsbudget gutgeschrieben.

## Creator-Modus (nur Admins)
- Superuser können Vereine, Spieler und Ligen direkt bearbeiten.

# Stadion-Kostenkalkulator

Du kannst auf Anfrage des Managers AUSSCHLIESSLICH Kosten berechnen — du gibst KEINE Empfehlungen, welche Tribüne oder welchen Typ er ausbauen soll. Das ist seine Entscheidung.

Wenn der Manager nach Ausbaukosten fragt (z.B. "Was kostet Ausbau auf 80.000?"), gehst du so vor:
1. Frage: Welche Tribüne? (Nordkurve / Osttribüne / Südkurve / Westtribüne)
2. Frage: Welcher Platztyp? (Stehplatz / Sitzplatz / VIP)
3. Berechne dann mit den Kosten aus dem Abschnitt "STADION-DATEN DES MANAGERS" die Gesamtkosten.

Formel: Anzahl neue Plätze × Kosten pro Platz (aus der Kostentabelle) = Gesamtkosten

Nenne immer die Gesamtkosten als konkreten Euro-Betrag (z.B. "Das kostet dich 24.000.000 €, Freund!").
Du DARFST NICHT sagen "das würde ich empfehlen" oder ähnliches — nur rechnen und präsentieren.
"""


def _build_stadium_context(user) -> str:
    """Inject the manager's current stadium data + cost matrix into the system prompt."""
    try:
        from game.views import current_manager_club
        from game.stadium_costs import get_kostenmatrix

        club = current_manager_club(user=user)
        if not club:
            return ""

        stadium = getattr(club, 'stadium', None)
        if not stadium:
            return ""

        cap = stadium.capacity_total
        matrix = get_kostenmatrix(cap)

        stands = [
            ("Nordkurve",   stadium.nord_standing,  stadium.nord_seating,  stadium.nord_vip),
            ("Osttribüne",  stadium.ost_standing,   stadium.ost_seating,   stadium.ost_vip),
            ("Südkurve",    stadium.sued_standing,  stadium.sued_seating,  stadium.sued_vip),
            ("Westtribüne", stadium.west_standing,  stadium.west_seating,  stadium.west_vip),
        ]

        lines = [
            f"\n\n# STADION-DATEN DES MANAGERS",
            f"Verein: {club.name}",
            f"Stadion: {stadium.name} ({stadium.city})",
            f"Gesamtkapazität: {cap:,} Plätze".replace(",", "."),
            f"  - Stehplätze gesamt: {stadium.capacity_standing:,}".replace(",", "."),
            f"  - Sitzplätze gesamt: {stadium.capacity_seating:,}".replace(",", "."),
            f"  - VIP gesamt:        {stadium.capacity_vip:,}".replace(",", "."),
            "",
            "Tribünen-Aufteilung:",
        ]
        for name, steh, sitz, vip in stands:
            total = steh + sitz + vip
            lines.append(
                f"  {name}: {total:,} gesamt (Steh {steh:,} | Sitz {sitz:,} | VIP {vip:,})".replace(",", ".")
            )

        lines += [
            "",
            "Aktuelle Kosten pro Platz (abhängig von Gesamtkapazität):",
            f"  Stehplatz: {matrix['STEH']:,.0f} € / Platz".replace(",", "."),
            f"  Sitzplatz: {matrix['SITZ']:,.0f} € / Platz".replace(",", "."),
            f"  VIP:       {matrix['VIP']:,.0f} € / Platz".replace(",", "."),
            "",
            f"Vereinsbudget: {float(club.budget):,.0f} €".replace(",", "."),
            f"Max. erlaubte Gesamtkapazität: 120.000 Plätze",
        ]
        return "\n".join(lines)

    except Exception:
        return ""


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

        stadium_context = _build_stadium_context(request.user)
        system_content = BASE_SYSTEM_PROMPT + stadium_context

        messages = [{'role': 'system', 'content': system_content}]
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
