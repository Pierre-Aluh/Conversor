import io
import json
import logging

from observabilidade import log_event


def test_log_event_sanitiza_caminho_de_arquivo():
    stream = io.StringIO()
    logger = logging.getLogger("test_observabilidade")
    logger.handlers = []
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

    log_event(
        logger,
        logging.ERROR,
        "falha_teste",
        etapa="conversao",
        arquivo=r"C:\\dados\\sigiloso\\lancamentos.xlsx",
    )

    payload = json.loads(stream.getvalue().strip())

    assert payload["evento"] == "falha_teste"
    assert payload["etapa"] == "conversao"
    assert payload["arquivo"] == "lancamentos.xlsx"
