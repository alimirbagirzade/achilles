"""İçeriksiz (boş / '...' placeholder) ama 'approved' kartları reddet — DB hijyeni.

NEDEN: 419 onaylı kartın ~198'i (title=None, main_claim='') içeriksiz olmasına rağmen
`approved` statüsünde; bu lora-audit'i FAIL gösterir ve coverage sayısını şişirir.
`build_dataset` bunları zaten eğitim verisine almaz (title boş → atlanır), yani eğitimi
ZEHİRLEMEZLER — sorun yalnız sayı/denetim hijyeni.

ÖNCE REBUILD DENE: RAG öğrenme döngüsü artık boş kartları sınırlı-retry ile YENİDEN üretir
(rag_learning_loop.py, commit 5a9f249). İçerik yeniden üretilebiliyorsa silmek YERİNE rebuild
tercih edilir. Bu script yalnız rebuild'in kurtaramadığı (bozuk-kaynak) ARTIK kartlar için,
rebuild'e şans verildikten SONRA çalıştırılmalıdır.

GÜVENLİK (CLAUDE.md kural 6 + 8):
  * Varsayılan DRY-RUN: hiçbir şey değiştirmez, yalnız raporlar.
  * Gerçek reddetme yalnız açık `--run` ile.
  * Kart SİLİNMEZ; review_status='rejected' yapılır (geri alınabilir: approve_card guard'ı
    artık boş kartı yeniden onaylamaz, ama içerik gelirse onaylanabilir).
  * LLM/ağ kullanmaz; deterministiktir.

Kullanım:
    uv run python scripts/purge_empty_cards.py            # dry-run (önizleme)
    uv run python scripts/purge_empty_cards.py --run       # gerçek reddetme
"""

from __future__ import annotations

import argparse

from app.memory.sqlite_store import SqliteStore, _card_has_content


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        action="store_true",
        help="Gerçekten reddet (varsayılan: dry-run, yalnız rapor).",
    )
    parser.add_argument(
        "--limit-preview",
        type=int,
        default=15,
        help="Dry-run'da gösterilecek örnek kart sayısı.",
    )
    args = parser.parse_args()

    store = SqliteStore()
    approved = store.list_approved_cards()
    empty = [c for c in approved if not _card_has_content(c.get("card_json") or {})]

    print(f"Onaylı kart: {len(approved)} | içeriksiz (boş/placeholder): {len(empty)}")
    if not empty:
        print("Temizlenecek kart yok. Çıkılıyor.")
        return 0

    for c in empty[: args.limit_preview]:
        title = (c.get("card_json") or {}).get("title")
        print(f"  - {c['card_id']} | paper={c.get('paper_id')} | title={title!r}")
    if len(empty) > args.limit_preview:
        print(f"  … +{len(empty) - args.limit_preview} kart daha")

    if not args.run:
        print("\nDRY-RUN: hiçbir şey değiştirilmedi. Gerçek reddetme için: --run")
        return 0

    rejected = sum(1 for c in empty if store.reject_card(c["card_id"]))
    print(f"\n✓ {rejected}/{len(empty)} içeriksiz kart 'rejected' yapıldı.")
    print("Doğrula: uv run achilles lora-audit  (artık FAIL'in boş-kart kısmı düşmeli)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
