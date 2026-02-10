from saturn.servers import ChatMessage, ChatRequest, chunk, completion


def test_chunk_structure():
    c = chunk("id-1", "llama3.2", {"content": "hello"})
    assert c["id"] == "id-1"
    assert c["object"] == "chat.completion.chunk"
    assert c["model"] == "llama3.2"
    assert c["choices"][0]["delta"] == {"content": "hello"}
    assert c["choices"][0]["finish_reason"] is None


def test_chunk_finish():
    c = chunk("id-1", "llama3.2", {}, finish=True)
    assert c["choices"][0]["finish_reason"] == "stop"
    assert c["choices"][0]["delta"] == {}


def test_completion_structure():
    c = completion("llama3.2", {"role": "assistant", "content": "hi"})
    assert c["object"] == "chat.completion"
    assert c["model"] == "llama3.2"
    assert c["choices"][0]["message"]["content"] == "hi"
    assert c["choices"][0]["finish_reason"] == "stop"
    assert "usage" not in c


def test_completion_with_usage():
    usage = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    c = completion("llama3.2", {"role": "assistant", "content": "hi"}, usage=usage)
    assert c["usage"] == usage


def test_chat_request_defaults():
    r = ChatRequest(model="m", messages=[ChatMessage(role="user", content="hi")])
    assert r.stream is False
    assert r.max_tokens is None
    assert r.temperature is None


def test_chat_request_full():
    r = ChatRequest(
        model="gpt-4",
        messages=[
            ChatMessage(role="system", content="you are helpful"),
            ChatMessage(role="user", content="hello"),
        ],
        max_tokens=100,
        stream=True,
        temperature=0.7,
    )
    assert r.model == "gpt-4"
    assert len(r.messages) == 2
    assert r.stream is True
    assert r.max_tokens == 100
    assert r.temperature == 0.7


def test_chat_message():
    m = ChatMessage(role="user", content="test")
    assert m.role == "user"
    assert m.content == "test"


def test_chunk_has_created():
    c = chunk("id", "m", {})
    assert isinstance(c["created"], int)
    assert c["created"] > 0
