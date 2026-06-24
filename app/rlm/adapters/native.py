"""Native RLM adapter — mevcut RlmController'ı sarar (VARSAYILAN motor).

Hiçbir ek bağımlılık gerektirmez (`rlms` paketi GEREKMEZ). Achilles'in çekirdek RLM
akışını (çok-turlu retrieval + iddia doğrulama + grounding + çekimser) aynen kullanır;
bu yüzden kaynaklı/doğrulanmış cevap, desteklenmeyen iddia atma ve "yeterli kaynak yok"
davranışı ZATEN buradadır. Adapter yalnız RLMRequest/RLMResponse sözleşmesine köprü kurar.
"""

from __future__ import annotations

from app.rlm.adapters.base import RLMRequest, RLMResponse


class NativeRLMAdapter:
    name = "native"

    def is_available(self) -> bool:
        return True  # çekirdek; her zaman kullanılabilir

    def complete(self, request: RLMRequest) -> RLMResponse:
        from app.rlm.rlm_controller import RlmController

        cfg = request.run_config or {}
        res = RlmController().answer(
            request.query,
            paper_ids=cfg.get("paper_ids"),
            top_k=cfg.get("top_k"),
            max_rounds=cfg.get("max_rounds"),
            write_report=bool(cfg.get("write_report", True)),
        )
        return RLMResponse(
            answer=res.final_answer,
            raw_response=res,
            metadata={
                "run_id": res.run_id,
                "task_type": res.task_type,
                "status": res.status,
                "confidence": res.final_confidence,
                "confidence_level": res.confidence_level,
                "evidence_score": res.evidence_score,
                "supported_claims": res.supported_claims,
                "unsupported_claims": res.unsupported_claims,
                "sources": res.sources,
            },
            used_adapter=self.name,
            success=res.status not in ("failed",),
        )
