REFUSAL = (
    "saturn.providers.hermes is a documented refusal stub.\n"
    "No NousResearch repo (Hermes-Function-Calling, atropos, hermes-agent, "
    "or ~78 others) ships an OpenAI-compatible inference server.\n"
    "hermes-agent itself is a CLIENT of OpenAI-compat endpoints, not a backend.\n"
    "See dist/research/repos/hermes.md.\n\n"
    "Recommended: serve Nous-trained Hermes weights through vLLM, llama.cpp, "
    "SGLang, or Ollama, and advertise that endpoint via Saturn instead."
)


def invoke(*args, **kwargs):
    raise NotImplementedError(REFUSAL)
