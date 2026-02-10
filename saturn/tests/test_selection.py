from saturn.discovery import SaturnService, select_best_service


def test_priority_selection(services):
    best = select_best_service(services, prefer_free=True)
    assert best.priority == min(s.priority for s in services)


def test_capability_filter(services):
    best = select_best_service(services, needs=["vision"], prefer_free=False)
    assert best.name == "high-priority"


def test_capability_filter_no_match(services):
    best = select_best_service(services, needs=["image_generation"])
    assert best is None


def test_context_filter(services):
    best = select_best_service(services, min_context=16000, prefer_free=False)
    assert best.name == "high-priority"
    assert best.context >= 16000


def test_context_filter_excludes_small(services):
    best = select_best_service(services, min_context=999999)
    assert best is None


def test_free_preference(services):
    best = select_best_service(services, prefer_free=True)
    assert best.name == "high-priority"


def test_free_preference_same_priority():
    paid = SaturnService(name="paid", host="h", port=1, priority=10, cost="paid")
    free = SaturnService(name="free", host="h", port=2, priority=10, cost="free")
    best = select_best_service([paid, free], prefer_free=True)
    assert best.name == "free"


def test_empty_list():
    assert select_best_service([]) is None


def test_combined_filters(services):
    best = select_best_service(services, needs=["chat", "code"], min_context=8000, prefer_free=True)
    assert best is not None
    assert best.has_all_capabilities(["chat", "code"])
    assert best.context >= 8000
