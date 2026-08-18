"""LangChain integration for SmartFabric / IFP.

A `FabricPressureCallback` that meters each LLM/tool call in a LangChain run and
reports it to a fabric node's pressure model. If the node escalates or denies,
the callback surfaces that so the chain can stop — turning IAIso containment into
a live guardrail around an agent, not just an after-the-fact audit.

This targets a RUNNING node (smartfabric serve). It is a thin adapter: all the
containment logic lives in the node, not here.

    from smartfabric_langchain import FabricPressureCallback
    cb = FabricPressureCallback(node_url="http://127.0.0.1:8770",
                                consent_token="<jwt>")
    llm.invoke("...", config={"callbacks": [cb]})

Requires: langchain-core (peer dependency; not vendored here).
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any

try:
    from langchain_core.callbacks import BaseCallbackHandler
except Exception:  # keep importable without langchain installed
    class BaseCallbackHandler:  # type: ignore
        pass


class FabricEscalation(RuntimeError):
    """Raised when the node escalates or denies — lets the chain abort."""


class FabricPressureCallback(BaseCallbackHandler):
    def __init__(self, node_url: str = "http://127.0.0.1:8770",
                 consent_token: str | None = None, raise_on_escalation: bool = True) -> None:
        self.node_url = node_url.rstrip("/")
        self.consent_token = consent_token
        self.raise_on_escalation = raise_on_escalation
        self.last: dict[str, Any] = {}

    # -- LangChain hooks --------------------------------------------------- #

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        tokens = self._tokens_from(response)
        self._meter(tokens=tokens, tool_calls=0)

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        self._meter(tokens=0, tool_calls=1)

    # -- fabric plumbing --------------------------------------------------- #

    def _meter(self, tokens: int, tool_calls: int) -> None:
        envelope = {
            "header": {"id": "01LC000000000000000000CALL", "verb": "invoke", "verb_version": "0.1",
                       "from": "iaiso://langchain@local/agent", "to": "iaiso://node@local/demo"},
            "policy": {},
            "auth": {"token": self.consent_token} if self.consent_token else {},
            "body": {"schema_ref": "invoke/1",
                     "payload": {"tokens": int(tokens), "tool_calls": int(tool_calls)}},
        }
        body = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
        req = urllib.request.Request(self.node_url + "/cir", data=body,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            reply = json.loads(resp.read())
        payload = reply.get("body", {}).get("payload", {})
        self.last = payload
        if "error" in payload:
            raise FabricEscalation(f"node denied call: {payload['error']}")
        if payload.get("escalation") and self.raise_on_escalation:
            raise FabricEscalation(f"fabric escalation at p={payload.get('p')}")

    @staticmethod
    def _tokens_from(response: Any) -> int:
        try:
            usage = response.llm_output.get("token_usage", {})
            return int(usage.get("total_tokens", 0))
        except Exception:
            return 0
