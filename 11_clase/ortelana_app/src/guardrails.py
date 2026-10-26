"""NeMo Guardrails wrapper: input rails before the graph, output rails after it."""

from dataclasses import dataclass
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.integrations.langchain.llm_adapter import LangChainLLMAdapter
from nemoguardrails.rails.llm.options import RailStatus, RailType

from src.retrieval import tokenize


@dataclass(frozen=True)
class Verdict:
    passed: bool
    message: str  # the original text when passed, otherwise the reply for the user


class _GeminiSafeAdapter(LangChainLLMAdapter):
    """NeMo binds `max_tokens` to every self-check call; Gemini only accepts `max_output_tokens`."""

    def _prepare_call_params(self, stop, kwargs):
        params = super()._prepare_call_params(stop, kwargs)
        if isinstance(self._llm, ChatGoogleGenerativeAI) and "max_tokens" in params:
            params["max_output_tokens"] = params.pop("max_tokens")
        return params


class Guardrails:
    def __init__(self, rails: LLMRails) -> None:
        self.rails = rails

    async def check_input(self, text: str) -> Verdict:
        return await self._check([{"role": "user", "content": text}], RailType.INPUT)

    async def check_output(self, question: str, answer: str) -> Verdict:
        messages = [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]
        return await self._check(messages, RailType.OUTPUT)

    async def _check(self, messages: list[dict], rail_type: RailType) -> Verdict:
        result = await self.rails.check_async(messages, rail_types=[rail_type])
        return Verdict(result.status != RailStatus.BLOCKED, result.content)


def build_guardrails(config_dir: Path, llm: BaseChatModel, competitors: list[str]) -> Guardrails:
    names = [" ".join(tokenize(name)) for name in competitors]

    async def mentions_competitor(context: dict) -> bool:
        text = f" {' '.join(tokenize(context.get('user_message', '')))} "
        return any(f" {name} " in text for name in names)

    rails = LLMRails(RailsConfig.from_path(str(config_dir)), llm=_GeminiSafeAdapter(llm))
    rails.register_action(mentions_competitor, name="mentions_competitor")
    return Guardrails(rails)
