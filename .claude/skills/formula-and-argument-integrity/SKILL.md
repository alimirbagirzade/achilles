# Formula and Argument Integrity Skill

## Amaç
LaTeX formüllerin sözdizimsel bütünlüğünü ve argüman zincirlerinin
mantıksal tamlığını doğrula; eksiklik tespit edildiğinde komşu chunk'ı öner.

## Tetiklenme Koşulları
- Chunk metninde LaTeX formülü tespit edildiğinde
- "eksik formül", "yarım denklem", "incomplete formula" gibi işaretçiler görüldüğünde
- Argüman zinciri (öncül → sonuç) kesintiye uğradığında

## Formül Bütünlüğü Kontrolü

### LaTeX Delimiter Dengesi
Aşağıdaki eşleştirilmiş çiftlerin dengeli olduğunu doğrula:
- `$...$` (inline)
- `$$...$$` (display)
- `\(...\)` (inline paren)
- `\[...\]` (display bracket)
- `\begin{equation}...\end{equation}`

```python
from app.verification.formula_verifier import FormulaVerifier
from app.memory.retrieval_service import RetrievedChunk

verifier = FormulaVerifier()
checks = verifier.verify_chunk(chunk)
for check in checks:
    if not check.is_complete:
        print(f"EKSIK FORMÜL: {check.formula_text[:100]}")
        print(f"Eksik değişkenler: {check.missing_variables}")
```

### Otomatik Tamamlama Yasağı
Formül eksikse asla tamamlama yapmayın. Bunun yerine:
1. Önceki/sonraki chunk'ta devamı ara
2. Kullanıcıya uyarı ver: "Bu formül kaynak metinde tamamlanmamış"

## Argüman Bütünlüğü Kontrolü

### Öncül-Sonuç Zinciri
Türkçe: dolayısıyla, bu nedenle, zira, çünkü
İngilizce: therefore, thus, since, because, hence

```python
from app.verification.argument_verifier import ArgumentVerifier

verifier = ArgumentVerifier()
result = verifier.verify(chunk.text)

if result.has_premise and not result.has_conclusion:
    print("Argüman başladı ama sonuca ulaşmadı — sonraki chunk'a bak")
elif not result.has_premise and result.has_conclusion:
    print("Sonuç var ama öncül yok — önceki chunk'a bak")
```

## Bağlamsal Chunker ile Entegrasyon
```python
from app.memory.contextual_chunker import ContextualChunker

annotator = ContextualChunker()
flags = annotator.annotate(chunks)

for flag in flags:
    if flag.needs_adjacent_context:
        print(f"{flag.chunk_id} komşu bağlam gerektiriyor")
        print(f"  Önceki: {flag.previous_chunk_id}")
        print(f"  Sonraki: {flag.next_chunk_id}")
```

## Rapor Formatı
```
[FORMÜL BÜTÜNLÜK RAPORU]
Toplam formül: N
  Tam: M
  Eksik: K
    - chunk_id: formül_özeti...

[ARGÜMAN ZİNCİRİ RAPORU]
Toplam argüman içeren chunk: N
  Tam zincir: M
  Eksik öncül: K
  Eksik sonuç: J
```
