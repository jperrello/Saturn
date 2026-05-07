REJECTED = {
    "hermes": (
        "Saturn cannot advertise 'hermes' as a backend.\n\n"
        "No NousResearch repo ships an OpenAI-compatible inference server. "
        "hermes-agent is itself a CLIENT of OpenAI-compat endpoints, not a backend.\n"
        "See dist/research/repos/hermes.md for the full negative finding.\n\n"
        "Recommended path: wrap Nous-trained Hermes weights with a real "
        "inference server — vLLM, llama.cpp, SGLang, or Ollama — and "
        "advertise THAT through Saturn (saturn run ollama / saturn config new)."
    ),
    "hermes-agent": (
        "Saturn cannot advertise 'hermes-agent' as a backend.\n\n"
        "hermes-agent is an OpenAI-compat CLIENT (a chat/agent runtime), "
        "not an OpenAI-compat server. Routing /v1/* requests TO it is incoherent.\n"
        "See dist/research/repos/hermes.md for the negative finding.\n\n"
        "If you want Hermes-trained weights served on the LAN, host them "
        "with vLLM, llama.cpp, SGLang, or Ollama and advertise that endpoint."
    ),
}


def check(name: str) -> str:
    return REJECTED.get(name, "")
