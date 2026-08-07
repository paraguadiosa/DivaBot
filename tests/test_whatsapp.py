"""Unit tests for the WhatsApp frontend logic (no bridge/network required)."""

import bot_whatsapp


def test_is_allowed_empty_allowlist_allows_everything(monkeypatch):
    monkeypatch.setattr(bot_whatsapp, "ALLOWED_USERS", set())
    assert bot_whatsapp._is_allowed("5491158432267@s.whatsapp.net", "5491158432267@s.whatsapp.net")
    assert bot_whatsapp._is_allowed("999999@s.whatsapp.net", "999999@s.whatsapp.net")


def test_is_allowed_matches_number(monkeypatch):
    monkeypatch.setattr(bot_whatsapp, "ALLOWED_USERS", {"5491158432267"})
    assert bot_whatsapp._is_allowed("5491158432267@s.whatsapp.net", "x")
    assert not bot_whatsapp._is_allowed("5491111111111@s.whatsapp.net", "x")


def test_is_allowed_ignores_plus_prefix(monkeypatch):
    monkeypatch.setattr(bot_whatsapp, "ALLOWED_USERS", {"5491158432267"})
    assert bot_whatsapp._is_allowed("+5491158432267@s.whatsapp.net", "x")


def test_handle_event_skips_empty_and_media(monkeypatch):
    monkeypatch.setattr(bot_whatsapp, "send_text", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not send")))
    import asyncio

    asyncio.run(bot_whatsapp.handle_event({"messageId": "1", "body": "", "chatId": "x@y"}))
    asyncio.run(bot_whatsapp.handle_event({"messageId": "2", "body": "", "hasMedia": True, "chatId": "x@y"}))


def test_handle_event_skips_from_owner(monkeypatch):
    import asyncio

    monkeypatch.setattr(bot_whatsapp, "send_text", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not send")))
    asyncio.run(bot_whatsapp.handle_event({"messageId": "3", "body": "hi", "fromOwner": True, "chatId": "x@y"}))


def test_handle_event_replies(monkeypatch):
    import asyncio

    sent = {}

    def fake_ask(prompt):
        return f"answer:{prompt}"

    def fake_send(chat_id, text, reply_to=None):
        sent["chat_id"] = chat_id
        sent["text"] = text
        sent["reply_to"] = reply_to

    monkeypatch.setattr(bot_whatsapp, "ask_llm", fake_ask)
    monkeypatch.setattr(bot_whatsapp, "send_text", fake_send)
    monkeypatch.setattr(bot_whatsapp, "send_typing", lambda chat_id: None)
    monkeypatch.setattr(bot_whatsapp, "ALLOWED_USERS", set())
    monkeypatch.setattr(bot_whatsapp, "_PROCESSED_IDS", set())

    asyncio.run(bot_whatsapp.handle_event(
        {"messageId": "42", "body": "hola", "chatId": "5491158432267@s.whatsapp.net", "senderId": "same"}
    ))
    assert sent["text"] == "answer:hola"
    assert sent["chat_id"] == "5491158432267@s.whatsapp.net"
    assert sent["reply_to"] == "42"
