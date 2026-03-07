from triadllm.i18n import Translator


def test_translator_falls_back_to_english() -> None:
    translator = Translator("es")
    value = translator.t("nonexistent.key")
    assert value == "nonexistent.key"

    assert translator.t("button.send") == "Enviar"
