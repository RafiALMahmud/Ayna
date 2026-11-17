from fastapi import APIRouter, Depends, HTTPException

from app.common.config import get_settings
from app.common.db import get_db
from app.modules.rag.schemas import ChatIn, ChatOut
from app.modules.rag.service import (
    card,
    filtered_products,
    grounded_answer,
    parse_filters,
    semantic_products,
)

router = APIRouter(prefix="/chat", tags=["Local product assistant"])


@router.get("/health")
def health():
    settings = get_settings()
    return {
        "enabled": settings.rag_enabled,
        "provider": "local-ollama" if settings.rag_enabled else "disabled",
        "model": settings.ollama_chat_model if settings.rag_enabled else None,
    }


@router.post("/search", response_model=ChatOut)
def search(body: ChatIn, db=Depends(get_db)):
    settings = get_settings()
    if not settings.rag_enabled:
        raise HTTPException(503, "The local product assistant is disabled")
    filters = parse_filters(body.message)
    structured = bool(filters.public())
    candidates = filtered_products(db, filters, max(settings.rag_max_results * 4, 24))
    semantic = False
    if not structured:
        candidates, semantic = semantic_products(
            db, body.message, candidates, settings.rag_max_results
        )
    else:
        candidates = candidates[: settings.rag_max_results]
    products = [card(db, product) for product in candidates]
    answer, generated = grounded_answer(body.message, products)
    mode = (
        "ollama-rag" if generated else ("semantic-fallback" if semantic else "deterministic-search")
    )
    return ChatOut(
        answer=answer,
        products=products,
        mode=mode,
        filters=filters.public(),
        suggestions=[
            "Show the cheapest shirts",
            "Which items have 3D views?",
            "১৫০০ টাকার মধ্যে কালো শার্ট দেখাও",
        ],
    )
