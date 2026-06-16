/* ACHILLES terminal — frontend logic (CSP-safe, harici dosya). */
(function () {
  "use strict";

  var TOKEN_KEY = "achilles_api_token";
  var MAX_UPLOAD_MB = 100; // backend varsayılanı (settings.max_upload_mb); /api/status'tan güncellenir
  // localStorage artifact ortamında engelli olabilir; güvenli sarmalayıcı:
  function getToken() {
    try {
      return window.localStorage.getItem(TOKEN_KEY) || "";
    } catch (e) {
      return window.__achillesToken || "";
    }
  }
  function setToken(t) {
    try {
      window.localStorage.setItem(TOKEN_KEY, t);
    } catch (e) {
      window.__achillesToken = t;
    }
  }

  function authHeaders(extra) {
    var h = extra || {};
    var t = getToken();
    if (t) h["Authorization"] = "Bearer " + t;
    return h;
  }

  function api(path, opts) {
    opts = opts || {};
    opts.headers = authHeaders(opts.headers);
    return fetch("/api" + path, opts).then(function (r) {
      if (r.status === 401) {
        toast("Yetkisiz — SİSTEM sekmesinden API token gir.", true);
        throw new Error("unauthorized");
      }
      if (r.status === 429) {
        toast("Hız sınırı aşıldı; biraz bekle.", true);
        throw new Error("rate-limited");
      }
      return r.json().then(function (body) {
        if (!r.ok) {
          throw new Error(body.detail || ("HTTP " + r.status));
        }
        return body;
      });
    });
  }

  // ---------- toast ----------
  var toastEl = document.getElementById("toast");
  var toastTimer = null;
  function toast(msg, isErr) {
    toastEl.textContent = msg;
    toastEl.className = "toast" + (isErr ? " err" : "");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      toastEl.className = "toast hidden";
    }, 3800);
  }

  function esc(s) {
    if (s === null || s === undefined) return "";
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  // ---------- tabs ----------
  var tabs = document.querySelectorAll(".tab");
  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      var name = tab.getAttribute("data-tab");
      tabs.forEach(function (t) {
        t.classList.remove("active");
      });
      tab.classList.add("active");
      document.querySelectorAll(".panel").forEach(function (p) {
        p.classList.remove("active");
      });
      document.getElementById("panel-" + name).classList.add("active");
      if (name === "papers") loadPapers();
      if (name === "trader") loadTraderBrain();
      if (name === "backtest") loadBacktestHistory();
      if (name === "training") loadTrainingStatus();
      if (name === "review") loadPendingCards();
      if (name === "eval") loadEvalSets();
      if (name === "about") loadSystemStatus();
    });
  });

  // ---------- adapter listesi (global, status'dan yüklenir) ----------
  var _adapters = [];

  function populateAdapterSelects(adapters) {
    _adapters = adapters || [];
    ["adapterSelect", "evalAdapterSelect"].forEach(function (id) {
      var sel = document.getElementById(id);
      if (!sel) return;
      var current = sel.value;
      while (sel.options.length > 1) sel.remove(1); // ilk "Ollama" seçeneği kalsın
      _adapters.forEach(function (a) {
        var opt = document.createElement("option");
        opt.value = a.version;
        opt.textContent = a.version + " (" + a.base_model.split("/").pop() + ")";
        sel.appendChild(opt);
      });
      sel.value = current;
    });
  }

  // ---------- status ----------
  function refreshStatus() {
    var dot = document.getElementById("connDot");
    var txt = document.getElementById("connText");
    api("/status", { method: "GET" })
      .then(function (s) {
        dot.className = "dot " + (s.ollama_available ? "dot-ok" : "dot-warn");
        txt.className = s.ollama_available ? "conn-ok" : "conn-warn";
        txt.textContent = s.ollama_available ? "ollama bağlı" : "ollama yok (RAG sınırlı)";
        document.getElementById("embedMode").textContent = "embed: " + s.embedding_mode;
        document.getElementById("paperCount").textContent = "papers: " + s.n_papers;
        if (s.max_upload_mb) {
          MAX_UPLOAD_MB = s.max_upload_mb;
          var pdfH = document.getElementById("pdfHint");
          var csvH = document.getElementById("csvHint");
          if (pdfH)
            pdfH.innerHTML =
              "yalnız .pdf · maks " +
              MAX_UPLOAD_MB +
              "&nbsp;MB · birden çok seçebilirsin · içerik doğrulanır";
          if (csvH)
            csvH.innerHTML =
              "kolonlar: time, open, high, low, close[, volume] · maks " +
              MAX_UPLOAD_MB +
              "&nbsp;MB · içerik doğrulanır";
        }
      })
      .catch(function () {
        dot.className = "dot dot-err";
        txt.className = "conn-err";
        txt.textContent = "sunucuya ulaşılamadı";
      });
    // adapter listesini de yükle
    api("/training/status", { method: "GET" })
      .then(function (d) { populateAdapterSelects(d.adapters || []); })
      .catch(function () {});
    // RAG ustalık % — kaç makaleyi içerik kartına dönüştürüp "anladı" + eğitim hazırlığı
    api("/rag-mastery", { method: "GET" })
      .then(function (m) {
        var el = document.getElementById("ragMastery");
        if (el) {
          var txt =
            "RAG anladı: %" + m.coverage_percent +
            " (" + m.papers_with_real + "/" + m.n_papers + ")";
          if (m.comprehension_percent != null) {
            // Kaba öz-değerlendirme — objektif değil; objektif skor için "obj. anlama" rozeti.
            txt += " · öz-değ. %" + m.comprehension_percent +
                   " (" + m.papers_scored + " makale)";
          }
          txt += " · eğitim %" + m.train_readiness_percent;
          el.textContent = txt;
        }
      })
      .catch(function () {});
  }

  // ---------- ask (RAG) ----------
  var askForm = document.getElementById("askForm");
  askForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = document.getElementById("question").value.trim();
    var topk = parseInt(document.getElementById("topk").value, 10) || null;
    if (q.length < 3) {
      toast("Soru çok kısa.", true);
      return;
    }
    var btn = document.getElementById("askBtn");
    var res = document.getElementById("askResult");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>SORGULANIYOR';
    res.className = "result";
    res.innerHTML =
      '<div class="result-section"><span class="spinner"></span> indeksten getiriliyor…</div>';

    var adapterSel = document.getElementById("adapterSelect");
    var adapterVersion = adapterSel ? (adapterSel.value || null) : null;
    api("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, top_k: topk, adapter_version: adapterVersion }),
    })
      .then(function (data) {
        renderAsk(res, data);
      })
      .catch(function (err) {
        res.innerHTML =
          '<div class="result-section result-body">Hata: ' + esc(err.message) + "</div>";
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = "SORGULA →";
      });
  });

  function renderAsk(res, data) {
    var badge = data.adapter_used
      ? '<span class="badge badge-adapter">LoRA: ' + esc(data.adapter_used) + "</span>"
      : data.llm_used
      ? '<span class="badge badge-llm">LLM cevabı</span>'
      : '<span class="badge badge-rag">yalnız kaynaklar (LLM yok)</span>';

    var srcHtml = "";
    if (data.sources && data.sources.length) {
      srcHtml = data.sources
        .map(function (s) {
          var page = s.page ? ", s." + s.page : "";
          var dist = s.distance != null ? "d=" + s.distance.toFixed(3) : "";
          return (
            '<div class="source-chip"><span class="cite">[' +
            esc(s.paper_id) +
            ":" +
            esc(s.chunk_id) +
            page +
            "]" +
            (s.title ? " — " + esc(s.title) : "") +
            '</span><span class="dist">' +
            dist +
            "</span></div>"
          );
        })
        .join("");
    } else {
      srcHtml = '<div class="muted small">Kaynak bulunamadı. Önce MAKALELER sekmesinden PDF ekle.</div>';
    }

    res.innerHTML =
      '<div class="result-section"><div class="result-label">durum</div>' +
      badge +
      ' <span class="muted small">embed: ' +
      esc(data.embedding_mode) +
      "</span></div>" +
      '<div class="result-section"><div class="result-label">cevap</div>' +
      '<div class="result-body">' +
      esc(data.answer) +
      "</div></div>" +
      '<div class="result-section"><div class="result-label">kaynaklar</div>' +
      '<div class="sources">' +
      srcHtml +
      "</div></div>";
  }

  // ---------- arXiv ----------
  var arxivSearchBtn = document.getElementById("arxivSearchBtn");
  var arxivFetchBtn  = document.getElementById("arxivFetchBtn");

  function getArxivParams() {
    var q = (document.getElementById("arxivQuery").value || "").trim();
    var max = parseInt(document.getElementById("arxivMax").value, 10) || 5;
    return { q: q, max: Math.min(Math.max(max, 1), 20) };
  }

  if (arxivSearchBtn) {
    arxivSearchBtn.addEventListener("click", function () {
      var p = getArxivParams();
      if (p.q.length < 3) { toast("Sorgu çok kısa.", true); return; }
      var res = document.getElementById("arxivResult");
      arxivSearchBtn.disabled = true;
      res.className = "result";
      res.innerHTML = '<div class="result-section"><span class="spinner"></span> arXiv aranıyor…</div>';
      api("/arxiv/search?q=" + encodeURIComponent(p.q) + "&max_results=" + p.max, { method: "GET" })
        .then(function (d) {
          if (!d.results || !d.results.length) {
            res.innerHTML = '<div class="result-section muted">Sonuç bulunamadı.</div>';
            return;
          }
          var rows = d.results.map(function (e) {
            return (
              '<div class="arxiv-row">' +
              '<div class="arxiv-title">' + esc(e.title) + '</div>' +
              '<div class="muted small">' + esc(e.arxiv_id) + ' · ' + esc(e.published) +
              (e.authors.length ? ' · ' + esc(e.authors.slice(0, 2).join(", ")) + (e.authors.length > 2 ? ' et al.' : '') : '') +
              '</div>' +
              '<div class="arxiv-abstract muted small">' + esc((e.abstract || "").slice(0, 180)) + '…</div>' +
              '</div>'
            );
          }).join("");
          res.innerHTML =
            '<div class="result-section"><div class="result-label">' + d.total + ' sonuç — "' + esc(d.query) + '"</div>' +
            rows + '</div>';
        })
        .catch(function (err) {
          res.innerHTML = '<div class="result-section">Hata: ' + esc(err.message) + '</div>';
        })
        .finally(function () { arxivSearchBtn.disabled = false; });
    });
  }

  if (arxivFetchBtn) {
    arxivFetchBtn.addEventListener("click", function () {
      var p = getArxivParams();
      if (p.q.length < 3) { toast("Sorgu çok kısa.", true); return; }
      var res = document.getElementById("arxivResult");
      arxivFetchBtn.disabled = true;
      arxivFetchBtn.innerHTML = '<span class="spinner"></span>İNDİRİLİYOR';
      res.className = "result";
      res.innerHTML = '<div class="result-section"><span class="spinner"></span> PDF\'ler indiriliyor + indeksleniyor…</div>';
      api("/arxiv/fetch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: p.q, max_results: p.max, auto_ingest: true }),
      })
        .then(function (d) {
          var rows = (d.results || []).map(function (r) {
            var badge = r.skipped
              ? '<span class="badge badge-warn">zaten var</span>'
              : '<span class="badge badge-success">indirildi</span>';
            return '<div class="arxiv-row">' + badge + ' ' + esc(r.arxiv_id) + ' — ' + esc(r.title) + '</div>';
          }).join("");
          res.innerHTML =
            '<div class="result-section"><div class="result-label">' + esc(d.message) + '</div>' +
            rows + '</div>';
          if (d.fetched > 0 || d.ingested > 0) {
            toast("arXiv: " + d.fetched + " indirildi, " + d.ingested + " indekslendi ✓");
            loadPapers(); // makale listesini yenile
          }
        })
        .catch(function (err) {
          res.innerHTML = '<div class="result-section">Hata: ' + esc(err.message) + '</div>';
        })
        .finally(function () {
          arxivFetchBtn.disabled = false;
          arxivFetchBtn.textContent = "⬇ İNDİR + İNDEKSLE";
        });
    });
  }

  // ---------- arXiv kayıtlı sorgular ----------
  function loadArxivQueries() {
    var el = document.getElementById("arxivQueriesList");
    if (!el) return;
    el.innerHTML = '<span class="spinner"></span>';
    api("/arxiv/queries", { method: "GET" })
      .then(function (d) {
        if (!d.queries || !d.queries.length) {
          el.innerHTML = '<p class="muted small">Henüz kayıtlı sorgu yok. Bir sorgu gir ve 📌 Sorguyu Kaydet\'e tıkla.</p>';
          return;
        }
        el.innerHTML = d.queries.map(function (q) {
          return '<div class="bt-card" style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">' +
            '<span style="flex:1"><b>' + esc(q.query) + '</b>' +
            '<span class="muted small"> · maks ' + q.max_results + ' · ' + q.run_count + ' çalıştırma' +
            (q.last_run_at ? ' · ' + new Date(q.last_run_at).toLocaleString("tr-TR") : '') + '</span></span>' +
            '<button class="btn btn-primary btn-run-query" data-qid="' + esc(q.query_id) + '" data-query="' + esc(q.query) + '">▶ Çalıştır</button>' +
            '<button class="btn btn-del-query" data-qid="' + esc(q.query_id) + '" style="color:#e55">✕</button>' +
            '</div>';
        }).join("");
        el.querySelectorAll(".btn-run-query").forEach(function (b) {
          b.addEventListener("click", function () { runArxivQuery(b.getAttribute("data-qid"), b.getAttribute("data-query"), b); });
        });
        el.querySelectorAll(".btn-del-query").forEach(function (b) {
          b.addEventListener("click", function () { deleteArxivQuery(b.getAttribute("data-qid")); });
        });
      })
      .catch(function () { el.innerHTML = '<p class="muted small">Sorgular yüklenemedi.</p>'; });
  }

  function runArxivQuery(qid, queryText, btn) {
    if (btn) { btn.disabled = true; btn.textContent = "…"; }
    api("/arxiv/queries/" + qid + "/run", { method: "POST" })
      .then(function (d) { toast("✓ " + d.message); loadArxivQueries(); })
      .catch(function (e) { toast("Hata: " + esc(e.message), true); })
      .finally(function () { if (btn) { btn.disabled = false; btn.textContent = "▶ Çalıştır"; } });
  }

  function deleteArxivQuery(qid) {
    api("/arxiv/queries/" + qid, { method: "DELETE" })
      .then(function () { loadArxivQueries(); })
      .catch(function (e) { toast("Silinemedi: " + esc(e.message), true); });
  }

  var arxivSaveBtn = document.getElementById("arxivSaveBtn");
  if (arxivSaveBtn) {
    arxivSaveBtn.addEventListener("click", function () {
      var q = (document.getElementById("arxivQuery").value || "").trim();
      var max = parseInt(document.getElementById("arxivMax").value, 10) || 5;
      if (!q) { toast("Önce bir sorgu gir.", true); return; }
      api("/arxiv/queries", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, max_results: max, auto_ingest: true }) })
        .then(function () { toast("Sorgu kaydedildi ✓"); loadArxivQueries(); })
        .catch(function (e) { toast("Kaydedilemedi: " + esc(e.message), true); });
    });
  }

  var refreshArxivQueries = document.getElementById("refreshArxivQueries");
  if (refreshArxivQueries) refreshArxivQueries.addEventListener("click", loadArxivQueries);
  loadArxivQueries();

  // ---------- papers ----------
  var _allPapers = [];
  var _comprehensionCache = {};

  function loadPapers() {
    var list = document.getElementById("papersList");
    list.innerHTML = '<div class="empty"><span class="spinner"></span> yükleniyor…</div>';
    api("/papers", { method: "GET" })
      .then(function (papers) {
        _allPapers = papers || [];
        renderPapers();
        loadComprehensionScores();
      })
      .catch(function (err) {
        document.getElementById("papersList").innerHTML =
          '<div class="empty">Hata: ' + esc(err.message) + "</div>";
      });
  }

  function renderPapers() {
    var list = document.getElementById("papersList");
    var query = (document.getElementById("paperSearch").value || "").toLowerCase();
    var filter = (document.querySelector(".filter-btn.active") || {}).getAttribute("data-filter") || "all";
    var sort = (document.getElementById("paperSort") || {}).value || "default";

    var visible = _allPapers.filter(function (p) {
      if (filter === "card" && !p.has_card) return false;
      if (filter === "nocard" && p.has_card) return false;
      if (query) {
        var title = (p.title || "").toLowerCase();
        var id = (p.paper_id || "").toLowerCase();
        if (title.indexOf(query) < 0 && id.indexOf(query) < 0) return false;
      }
      return true;
    });

    if (sort === "title-asc") {
      visible.sort(function (a, b) { return (a.title || "").localeCompare(b.title || ""); });
    } else if (sort === "title-desc") {
      visible.sort(function (a, b) { return (b.title || "").localeCompare(a.title || ""); });
    } else if (sort === "card-first") {
      visible.sort(function (a, b) { return (b.has_card ? 1 : 0) - (a.has_card ? 1 : 0); });
    } else if (sort === "nocard-first") {
      visible.sort(function (a, b) { return (a.has_card ? 1 : 0) - (b.has_card ? 1 : 0); });
    }

    if (!_allPapers.length) {
      list.innerHTML = '<div class="empty">Henüz makale yok. Yukarıdan PDF yükle.</div>';
      return;
    }
    if (!visible.length) {
      list.innerHTML = '<div class="empty">Filtreye uyan makale bulunamadı.</div>';
      return;
    }

    list.innerHTML = visible
      .map(function (p) {
        var btn = p.has_card
          ? '<button class="btn card-view" data-id="' + esc(p.paper_id) + '">✓ KARTI GÖR</button>'
          : '<button class="btn card-btn" data-id="' + esc(p.paper_id) + '">BİLGİ KARTI ÜRET</button>';
        var cached = _comprehensionCache[p.paper_id];
        var badgeLabel = (cached != null) ? cached + "%" : "?%";
        var badgeCls = "comp-badge" +
          (cached == null ? "" : (cached >= 80 ? " comp-high" : cached >= 50 ? " comp-mid" : " comp-low"));
        var badge = p.has_card
          ? '<button class="' + badgeCls + '" data-comp-id="' + esc(p.paper_id) + '" title="Anlama skoru — tıkla hesapla">' + badgeLabel + '</button>'
          : '';
        return (
          '<div class="paper-row' +
          (p.has_card ? " has-card" : "") +
          '"><div class="paper-meta">' +
          '<div class="paper-title">' +
          esc(p.title || "(başlıksız)") +
          "</div>" +
          '<div class="paper-id">' +
          esc(p.paper_id) +
          " · " +
          (p.n_chunks || 0) +
          " chunk" +
          (p.year ? " · " + esc(p.year) : "") +
          "</div></div>" +
          '<div class="paper-actions">' +
          badge +
          btn +
          "</div></div>"
        );
      })
      .join("");

    list.querySelectorAll(".card-btn").forEach(function (b) {
      b.addEventListener("click", function () {
        makeCard(b.getAttribute("data-id"), b);
      });
    });
    list.querySelectorAll(".card-view").forEach(function (b) {
      b.addEventListener("click", function () {
        viewCard(b.getAttribute("data-id"));
      });
    });
    list.querySelectorAll(".comp-badge").forEach(function (b) {
      b.addEventListener("click", function () {
        var pid = b.getAttribute("data-comp-id");
        b.textContent = "…";
        b.disabled = true;
        api("/papers/" + encodeURIComponent(pid) + "/comprehension", { method: "POST" })
          .then(function (d) {
            _comprehensionCache[pid] = d.total != null ? Math.round(d.total) : null;
            renderPapers();
          })
          .catch(function () {
            b.textContent = "?%";
            b.disabled = false;
          });
      });
    });
  }

  function loadComprehensionScores() {
    api("/papers/comprehension/all", { method: "GET" })
      .then(function (d) {
        var scores = (d && d.scores) ? d.scores : {};
        var changed = false;
        Object.keys(scores).forEach(function (pid) {
          if (_comprehensionCache[pid] !== scores[pid]) {
            _comprehensionCache[pid] = scores[pid];
            changed = true;
          }
        });
        if (changed) renderPapers();
      })
      .catch(function () {});
  }

  // filtre/sıralama olayları
  document.getElementById("paperSearch").addEventListener("input", renderPapers);
  document.getElementById("paperSort").addEventListener("change", renderPapers);
  document.getElementById("cardFilter").addEventListener("click", function (e) {
    var btn = e.target.closest(".filter-btn");
    if (!btn) return;
    document.querySelectorAll(".filter-btn").forEach(function (b) { b.classList.remove("active"); });
    btn.classList.add("active");
    renderPapers();
  });

  function makeCard(paperId, btn) {
    btn.disabled = true;
    btn.classList.remove("btn-err");
    btn.innerHTML = '<span class="spinner"></span>ÜRETİLİYOR';
    api("/card/" + encodeURIComponent(paperId), { method: "POST" })
      .then(function (data) {
        toast("Bilgi kartı üretildi: " + paperId);
        if (data && data.card) renderCard(data.card, paperId); // hemen göster
        loadPapers(); // liste yenilensin → 'KARTI GÖR'
      })
      .catch(function (err) {
        toast(err.message, true);
        btn.classList.add("btn-err");
        btn.textContent = "✕ HATA — TEKRAR DENE";
        btn.disabled = false;
      });
  }

  // ---------- bilgi kartı görüntüleme ----------
  var cardModal = document.getElementById("cardModal");
  var cardBody = document.getElementById("cardBody");

  function showCardModal() {
    cardModal.classList.remove("hidden");
  }
  function hideCardModal() {
    cardModal.classList.add("hidden");
  }
  document.getElementById("cardClose").addEventListener("click", hideCardModal);
  cardModal.addEventListener("click", function (e) {
    if (e.target === cardModal) hideCardModal(); // dışına tıkla → kapat
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") hideCardModal();
  });

  function viewCard(paperId) {
    cardBody.innerHTML = '<div class="muted"><span class="spinner"></span> kart yükleniyor…</div>';
    showCardModal();
    api("/card/" + encodeURIComponent(paperId), { method: "GET" })
      .then(function (data) {
        renderCard(data.card, paperId);
      })
      .catch(function (err) {
        cardBody.innerHTML = '<div class="result-body">Hata: ' + esc(err.message) + "</div>";
      });
  }

  function _kcText(label, val) {
    if (!val) return "";
    return (
      '<div class="kc-field"><div class="kc-label">' +
      esc(label) +
      '</div><p>' +
      esc(val) +
      "</p></div>"
    );
  }
  function _kcList(label, arr) {
    if (!arr || !arr.length) return "";
    var items = arr
      .map(function (x) {
        return "<li>" + esc(x) + "</li>";
      })
      .join("");
    return (
      '<div class="kc-field"><div class="kc-label">' +
      esc(label) +
      '</div><ul>' +
      items +
      "</ul></div>"
    );
  }

  function renderCard(c, paperId) {
    c = c || {};
    var meta = [c.year, c.domain].filter(Boolean).map(esc).join(" · ");
    var hasHyps = c.possible_strategy_hypotheses && c.possible_strategy_hypotheses.length;
    var btBtn = paperId && hasHyps
      ? '<button class="btn btn-hyp-bt" id="hypBtBtn" data-id="' + esc(paperId) + '">⚡ HİPOTEZLERİ BACKTEST ET</button>'
      : "";
    cardBody.innerHTML =
      '<h3 class="kc-title">' +
      esc(c.title || "(başlıksız)") +
      "</h3>" +
      (meta ? '<div class="kc-meta">' + meta + "</div>" : "") +
      _kcText("Ana bulgu", c.main_claim) +
      _kcText("Trading ilgisi", c.trading_relevance) +
      _kcList("Yöntemler", c.methods) +
      _kcList("Veri setleri", c.datasets) +
      _kcList("Strateji hipotezleri", c.possible_strategy_hypotheses) +
      _kcList("Risk uyarıları", c.risk_warnings) +
      _kcList("Sınırlamalar", c.limitations) +
      _kcList("Uygulama notları", c.implementation_notes) +
      (btBtn ? '<div class="kc-bt-bar">' + btBtn + '<div id="hypBtResult"></div></div>' : "");
    showCardModal();

    if (paperId && hasHyps) {
      var hypBtBtn = document.getElementById("hypBtBtn");
      if (hypBtBtn) hypBtBtn.addEventListener("click", function () {
        backtestFromCard(paperId);
      });
    }
  }

  function backtestFromCard(paperId) {
    var btn = document.getElementById("hypBtBtn");
    var res = document.getElementById("hypBtResult");
    if (!btn || !res) return;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>ÇALIŞIYOR';
    res.innerHTML = "";
    api("/card/" + encodeURIComponent(paperId) + "/backtest", { method: "POST" })
      .then(function (data) {
        btn.textContent = "✓ TAMAMLANDI";
        res.innerHTML = renderHypBacktest(data);
      })
      .catch(function (err) {
        btn.disabled = false;
        btn.textContent = "⚡ HİPOTEZLERİ BACKTEST ET";
        res.innerHTML = '<div class="kc-bt-err">Hata: ' + esc(err.message) + "</div>";
      });
  }

  function renderHypBacktest(data) {
    if (!data.results || !data.results.length) return '<div class="muted">Sonuç yok.</div>';
    return data.results
      .map(function (r) {
        var m = r.metrics || {};
        var vClass = "verdict-" + (r.verdict || "inconclusive");
        var vLabel = { pass: "GEÇTİ", fail: "BAŞARISIZ", inconclusive: "SONUÇSUZ" }[r.verdict] || r.verdict;
        var reasons = (r.reasons || []).map(function (x) { return "<li>" + esc(x) + "</li>"; }).join("");
        var keyMetrics = ["total_return_pct", "sharpe", "max_drawdown_pct", "win_rate_pct", "n_trades"];
        var metricHtml = keyMetrics
          .filter(function (k) { return k in m; })
          .map(function (k) {
            var labels = { total_return_pct: "getiri%", sharpe: "sharpe", max_drawdown_pct: "maxDD%", win_rate_pct: "win%", n_trades: "işlem" };
            var v = Number(m[k]).toFixed(k === "n_trades" ? 0 : 3);
            var cls = (k === "total_return_pct" || k === "sharpe") ? (m[k] > 0 ? " pos" : " neg") : (k === "max_drawdown_pct" ? " neg" : "");
            return '<div class="metric"><div class="k">' + (labels[k] || k) + '</div><div class="v' + cls + '">' + esc(v) + "</div></div>";
          })
          .join("");
        return (
          '<div class="hyp-row">' +
          '<div class="hyp-text">' + esc(r.hypothesis) + "</div>" +
          '<div class="metrics-grid">' + metricHtml + "</div>" +
          '<div class="verdict ' + vClass + '"><b>' + vLabel + "</b><ul>" + reasons + "</ul></div>" +
          "</div>"
        );
      })
      .join("");
  }

  // ---------- eğitim sekmesi ----------
  function loadTrainingStatus() {
    api("/training/status", { method: "GET" })
      .then(function (data) {
        var el = document.getElementById("trainingStatus");
        if (el) {
          el.innerHTML =
            '<div class="training-stat">' +
            '<span class="kc-label">Eğitim örnekleri</span> ' +
            '<strong>' + data.n_examples + '</strong>' +
            '</div>';
        }
        renderAdapters(data.adapters || []);
        populateAdapterSelects(data.adapters || []);
        loadExamples();
      })
      .catch(function (err) {
        var el = document.getElementById("trainingStatus");
        if (el) el.innerHTML = '<span class="conn-err">Hata: ' + esc(err.message) + "</span>";
      });
  }

  function renderAdapters(adapters) {
    var el = document.getElementById("adaptersList");
    if (!el) return;
    if (!adapters.length) {
      el.innerHTML = '<div class="empty">Henüz kayıtlı adapter yok.</div>';
      return;
    }
    el.innerHTML = adapters
      .map(function (a) {
        return (
          '<div class="adapter-row">' +
          '<div class="adapter-version">' + esc(a.version) + "</div>" +
          '<div class="adapter-meta">' +
          esc(a.base_model) +
          (a.created_at ? " · " + esc(a.created_at.slice(0, 10)) : "") +
          (a.notes ? " · " + esc(a.notes) : "") +
          "</div></div>"
        );
      })
      .join("");
  }

  // ---------- eğitim örnekleri ----------
  function loadExamples() {
    var el = document.getElementById("examplesList");
    if (!el) return;
    el.innerHTML = '<div class="empty"><span class="spinner"></span> yükleniyor…</div>';
    api("/training/examples", { method: "GET" })
      .then(function (data) {
        var examples = data.examples || [];
        if (!examples.length) {
          el.innerHTML = '<div class="empty">Henüz eğitim örneği yok.</div>';
          return;
        }
        el.innerHTML =
          '<div class="examples-count">' + examples.length + " örnek</div>" +
          examples
            .map(function (ex) {
              return (
                '<div class="example-row" data-id="' + esc(ex.example_id) + '">' +
                '<div class="example-header">' +
                '<span class="example-type">' + esc(ex.example_type) + "</span>" +
                (ex.source_paper_id ? '<span class="example-paper">' + esc(ex.source_paper_id) + "</span>" : "") +
                '<span class="example-date muted">' + esc((ex.created_at || "").slice(0, 10)) + "</span>" +
                '<button class="btn btn-del-example" data-id="' + esc(ex.example_id) + '" title="Sil">✕</button>' +
                "</div>" +
                '<div class="example-instruction">' + esc(ex.instruction.slice(0, 120)) + (ex.instruction.length > 120 ? "…" : "") + "</div>" +
                "</div>"
              );
            })
            .join("");
        el.querySelectorAll(".btn-del-example").forEach(function (b) {
          b.addEventListener("click", function (e) {
            e.stopPropagation();
            deleteExample(b.getAttribute("data-id"));
          });
        });
      })
      .catch(function (err) {
        el.innerHTML = '<div class="empty">Hata: ' + esc(err.message) + "</div>";
      });
  }

  function deleteExample(exampleId) {
    api("/training/examples/" + encodeURIComponent(exampleId), { method: "DELETE" })
      .then(function () {
        toast("Örnek silindi.");
        loadExamples();
        loadTrainingStatus();
      })
      .catch(function (err) {
        toast("Silinemedi: " + err.message, true);
      });
  }

  var refreshExamples = document.getElementById("refreshExamples");
  if (refreshExamples) refreshExamples.addEventListener("click", loadExamples);

  var buildDatasetBtn = document.getElementById("buildDatasetBtn");
  if (buildDatasetBtn) {
    buildDatasetBtn.addEventListener("click", function () {
      buildDatasetBtn.disabled = true;
      buildDatasetBtn.innerHTML = '<span class="spinner"></span>OLUŞTURULUYOR';
      var res = document.getElementById("datasetResult");
      res.className = "result";
      res.innerHTML = '<div class="result-section"><span class="spinner"></span></div>';
      api("/training/dataset", { method: "POST" })
        .then(function (data) {
          toast(data.message);
          res.innerHTML =
            '<div class="result-section"><div class="result-label">sonuç</div>' +
            '<div class="result-body">' +
            esc(data.message) +
            " · hash: " + esc(data.content_hash) +
            "</div></div>";
          loadTrainingStatus();
        })
        .catch(function (err) {
          toast(err.message, true);
          res.innerHTML = '<div class="result-section result-body">Hata: ' + esc(err.message) + "</div>";
        })
        .finally(function () {
          buildDatasetBtn.disabled = false;
          buildDatasetBtn.textContent = "DATASET OLUŞTUR";
        });
    });
  }

  // ---------- Canlı Eğitim UI ----------
  var _trainESS = null;

  function applyTrainProgress(d) {
    var stateMap = { idle: "boşta", running: "eğitiliyor…", completed: "tamamlandı ✓", failed: "hata ✗", stopped: "durduruldu" };
    var stateColors = { idle: "badge-info", running: "badge-warn", completed: "badge-success", failed: "badge-error", stopped: "badge-info" };
    var label = document.getElementById("trainStateLabel");
    if (label) {
      label.textContent = stateMap[d.state] || d.state;
      label.className = "badge " + (stateColors[d.state] || "badge-info");
    }
    var isRunning = d.state === "running";
    var startBtn = document.getElementById("startTrainBtn");
    var stopBtn = document.getElementById("stopTrainBtn");
    if (startBtn) startBtn.style.display = isRunning ? "none" : "";
    if (stopBtn) stopBtn.style.display = isRunning ? "" : "none";

    var section = document.getElementById("trainProgressSection");
    if (section && d.state !== "idle") section.style.display = "";

    var bar = document.getElementById("trainProgressBar");
    var pctLbl = document.getElementById("trainPctLabel");
    var iterLbl = document.getElementById("trainIterLabel");
    if (bar) bar.style.width = (d.pct || 0) + "%";
    if (pctLbl) pctLbl.textContent = (d.pct || 0).toFixed(1) + "%";
    if (iterLbl) iterLbl.textContent = (d.current_iter || 0) + " / " + (d.total_iters || 0) + " iter";

    var tl = document.getElementById("trainLossVal");
    var vl = document.getElementById("valLossVal");
    if (tl) tl.textContent = d.train_loss != null ? Number(d.train_loss).toFixed(4) : "—";
    if (vl) vl.textContent = d.val_loss != null ? Number(d.val_loss).toFixed(4) : "—";

    var meta = document.getElementById("trainMeta");
    if (meta && d.adapter_name) {
      meta.textContent = "Adapter: " + d.adapter_name +
        (d.started_at ? "  ·  Başladı: " + d.started_at : "") +
        (d.finished_at && d.state !== "running" ? "  ·  Bitti: " + d.finished_at : "");
    }
  }

  function appendLog(line) {
    var el = document.getElementById("trainLog");
    if (!el) return;
    el.textContent += line + "\n";
    el.scrollTop = el.scrollHeight;
  }

  function startSSE() {
    if (_trainESS) { _trainESS.close(); _trainESS = null; }
    var tok = getToken();
    var url = "/api/training/stream" + (tok ? "?token=" + encodeURIComponent(tok) : "");
    _trainESS = new EventSource(url);
    _trainESS.onmessage = function (e) {
      try {
        var d = JSON.parse(e.data);
        if (d.line) appendLog(d.line);
        applyTrainProgress(d);
        if (d.type === "done" || d.type === "stopped") {
          _trainESS.close();
          _trainESS = null;
          loadTrainingStatus();
        }
      } catch (_) {}
    };
    _trainESS.onerror = function () {
      if (_trainESS) { _trainESS.close(); _trainESS = null; }
    };
  }

  var startTrainBtn = document.getElementById("startTrainBtn");
  if (startTrainBtn) {
    startTrainBtn.addEventListener("click", function () {
      var payload = {
        base_model: (document.getElementById("drBaseModel") || {}).value || "",
        adapter_name: (document.getElementById("trAdapterName") || {}).value || "achilles_lora",
        iterations: parseInt((document.getElementById("drIterations") || {}).value, 10) || 500,
        batch_size: parseInt((document.getElementById("drBatch") || {}).value, 10) || 2,
        num_layers: parseInt((document.getElementById("drLayers") || {}).value, 10) || 8,
        learning_rate: 1e-4,
      };
      var section = document.getElementById("trainProgressSection");
      if (section) section.style.display = "";
      var logEl = document.getElementById("trainLog");
      if (logEl) logEl.textContent = "";
      api("/training/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) })
        .then(function (data) {
          toast(data.message, !data.ok);
          // Detached eğitim: SSE yerine /api/training/live poll'u (mirrorTrainTab) besler.
          if (data.ok) refreshTrain();
        })
        .catch(function (err) { toast(err.message, true); });
    });
  }

  var stopTrainBtn = document.getElementById("stopTrainBtn");
  if (stopTrainBtn) {
    stopTrainBtn.addEventListener("click", function () {
      api("/training/stop", { method: "POST" })
        .then(function () { toast("Eğitim durduruldu."); })
        .catch(function () {});
    });
  }

  var clearLogBtn = document.getElementById("clearLogBtn");
  if (clearLogBtn) {
    clearLogBtn.addEventListener("click", function () {
      var el = document.getElementById("trainLog");
      if (el) el.textContent = "";
    });
  }

  var refreshAdapters = document.getElementById("refreshAdapters");
  if (refreshAdapters) refreshAdapters.addEventListener("click", loadTrainingStatus);

  // Sayfa açılışında mevcut durumu çek; training devam ediyorsa SSE başlat
  api("/training/progress", { method: "GET" })
    .then(function (d) {
      applyTrainProgress(d);
      if (d.state === "running") startSSE();
    })
    .catch(function () {});

  // ---------- toplu kart üretimi ----------
  var batchCardBtn = document.getElementById("batchCardBtn");
  if (batchCardBtn) {
    batchCardBtn.addEventListener("click", function () {
      batchCardBtn.disabled = true;
      batchCardBtn.innerHTML = '<span class="spinner"></span>ÜRETİLİYOR…';
      var res = document.getElementById("batchCardResult");
      res.className = "result";
      res.innerHTML = '<div class="result-section"><span class="spinner"></span> Kartlar üretiliyor (LLM gerekli, her makale ~60s)…</div>';
      api("/cards/batch", { method: "POST" })
        .then(function (data) {
          toast(data.produced + " kart üretildi, " + data.skipped + " atlandı, " + data.errors + " hata.");
          var rows = (data.results || []).map(function (r) {
            var cls = r.status === "ok" ? "pos" : r.status === "error" ? "neg" : "muted";
            return (
              '<div class="batch-row">' +
              '<span class="' + cls + '">' + esc(r.status.toUpperCase()) + "</span> " +
              "<b>" + esc(r.title || r.paper_id) + "</b> — " +
              esc(r.message) +
              "</div>"
            );
          }).join("");
          res.innerHTML =
            '<div class="result-section"><div class="result-label">sonuç</div>' +
            "<div>" + rows + "</div></div>";
          loadPapers();
        })
        .catch(function (err) {
          toast(err.message, true);
          res.innerHTML = '<div class="result-section result-body">Hata: ' + esc(err.message) + "</div>";
        })
        .finally(function () {
          batchCardBtn.disabled = false;
          batchCardBtn.textContent = "⚡ TÜM KARTLARI ÜRET";
        });
    });
  }

  // ---------- toplu skor hesaplama ----------
  var batchScoreBtn = document.getElementById("batchScoreBtn");
  if (batchScoreBtn) {
    batchScoreBtn.addEventListener("click", function () {
      batchScoreBtn.disabled = true;
      batchScoreBtn.innerHTML = '<span class="spinner"></span>HESAPLANIYOR…';
      var res = document.getElementById("batchScoreResult");
      res.className = "result";
      res.innerHTML = '<div class="result-section"><span class="spinner"></span> Skorlar hesaplanıyor (LLM gerekli, her makale ~30s)…</div>';
      api("/papers/comprehension/batch", { method: "POST" })
        .then(function (data) {
          toast(data.computed + " skor hesaplandı, " + data.skipped + " atlandı, " + data.errors + " hata.");
          var rows = (data.results || []).map(function (r) {
            var cls = r.status === "ok" ? "pos" : r.status === "error" ? "neg" : "muted";
            var scoreStr = r.score != null ? " — " + Math.round(r.score) + "%" : "";
            return (
              '<div class="batch-row">' +
              '<span class="' + cls + '">' + esc(r.status.toUpperCase()) + "</span> " +
              "<b>" + esc(r.title || r.paper_id) + "</b>" +
              esc(scoreStr) + " " + esc(r.message) +
              "</div>"
            );
          }).join("");
          res.innerHTML =
            '<div class="result-section"><div class="result-label">sonuç</div>' +
            "<div>" + rows + "</div></div>";
          _comprehensionCache = {};
          loadPapers();
        })
        .catch(function (err) {
          toast(err.message, true);
          res.innerHTML = '<div class="result-section result-body">Hata: ' + esc(err.message) + "</div>";
        })
        .finally(function () {
          batchScoreBtn.disabled = false;
          batchScoreBtn.textContent = "🧪 TÜM SKORLARI HESAPLA";
        });
    });
  }

  // ---------- objektif anlama skoru (L3/L4 sınav geçme oranı, kaba %'nin yerine) ----------
  var objUnderstandingEl = document.getElementById("objUnderstanding");
  if (objUnderstandingEl) {
    objUnderstandingEl.addEventListener("click", function () {
      var prev = objUnderstandingEl.textContent;
      objUnderstandingEl.textContent = "obj. anlama: …";
      api("/understanding-score", { method: "GET" })
        .then(function (s) {
          if (s.status !== "scored" || s.pass_rate == null) {
            objUnderstandingEl.textContent = "obj. anlama: veri yok";
            objUnderstandingEl.title =
              "Objektif sınav notlanamadı (LLM çevrimdışı olabilir). Notlanan: " +
              s.graded + " · atlanan: " + s.skipped;
            toast("Objektif anlama: notlanan sınav yok (LLM çevrimdışı?).", true);
            return;
          }
          var pct = Math.round(s.pass_rate * 100);
          objUnderstandingEl.textContent = "obj. anlama %" + pct;
          objUnderstandingEl.title =
            "Objektif L3/L4 sınav geçme oranı — geçti " + s.passed + "/" + s.graded +
            " (atlanan " + s.skipped + ", veri yok " + s.no_data + ")";
          toast("Objektif anlama skoru: %" + pct + " (" + s.graded + " sınav)");
        })
        .catch(function (err) {
          objUnderstandingEl.textContent = prev;
          toast(err.message, true);
        });
    });
  }

  // ---------- çapraz makale sentezi ----------
  var crossSynthesisBtn = document.getElementById("crossSynthesisBtn");
  if (crossSynthesisBtn) {
    crossSynthesisBtn.addEventListener("click", function () {
      crossSynthesisBtn.disabled = true;
      crossSynthesisBtn.innerHTML = '<span class="spinner"></span>SENTEZLENİYOR…';
      var res = document.getElementById("crossSynthesisResult");
      res.className = "result";
      res.innerHTML =
        '<div class="result-section"><span class="spinner"></span> ' +
        'Formüller arası ilişkiler analiz ediliyor ve eğitim verisi üretiliyor…</div>';
      api("/synthesis/cross-paper", { method: "POST" })
        .then(function (data) {
          toast(data.message);
          var cls = data.produced > 0 ? "pos" : "muted";
          res.innerHTML =
            '<div class="result-section"><div class="result-label">sentez sonucu</div>' +
            '<div class="batch-row"><span class="' + cls + '">' +
            (data.produced > 0 ? "✓ " + data.produced + " yeni örnek" : "Güncel") +
            '</span> — ' + esc(data.message) + "</div></div>";
        })
        .catch(function (err) {
          toast(err.message, true);
          res.innerHTML =
            '<div class="result-section result-body">Hata: ' + esc(err.message) + "</div>";
        })
        .finally(function () {
          crossSynthesisBtn.disabled = false;
          crossSynthesisBtn.textContent = "🔗 ÇAPRAZ SENTEZ ÜRET";
        });
    });
  }

  document.getElementById("refreshPapers").addEventListener("click", loadPapers);
  document.getElementById("reindexBtn").addEventListener("click", function () {
    var b = this;
    b.disabled = true;
    b.innerHTML = '<span class="spinner"></span>İNDEKSLENİYOR';
    api("/ingest", { method: "POST" })
      .then(function (r) {
        toast(r.message);
        loadPapers();
        refreshStatus();
      })
      .catch(function (err) {
        toast(err.message, true);
      })
      .finally(function () {
        b.disabled = false;
        b.textContent = "⟳ TÜMÜNÜ İNDEKSLE";
      });
  });

  // ---------- upload ----------
  var zone = document.getElementById("uploadZone");
  var input = document.getElementById("pdfInput");
  document.getElementById("browseBtn").addEventListener("click", function (e) {
    e.stopPropagation();
    input.click();
  });
  zone.addEventListener("click", function () {
    input.click();
  });
  zone.addEventListener("dragover", function (e) {
    e.preventDefault();
    zone.classList.add("drag");
  });
  zone.addEventListener("dragleave", function () {
    zone.classList.remove("drag");
  });
  zone.addEventListener("drop", function (e) {
    e.preventDefault();
    zone.classList.remove("drag");
    if (e.dataTransfer.files && e.dataTransfer.files.length) {
      uploadFiles(e.dataTransfer.files);
    }
  });
  input.addEventListener("change", function () {
    if (input.files && input.files.length) uploadFiles(input.files);
    input.value = ""; // aynı dosyaları tekrar seçebilmek için sıfırla
  });

  // Birden çok PDF'i SIRAYLA yükler (8GB'ı zorlamamak için paralel DEĞİL).
  function uploadFiles(fileList) {
    var files = [];
    for (var k = 0; k < fileList.length; k++) {
      if (fileList[k].name.toLowerCase().endsWith(".pdf")) files.push(fileList[k]);
    }
    if (!files.length) {
      toast("Yalnız .pdf kabul edilir.", true);
      return;
    }
    var i = 0,
      ok = 0,
      fail = 0,
      dup = 0;
    function next() {
      if (i >= files.length) {
        done();
        return;
      }
      var f = files[i++];
      if (f.size > MAX_UPLOAD_MB * 1024 * 1024) {
        fail++;
        toast(f.name + " > " + MAX_UPLOAD_MB + " MB, atlandı.", true);
        return next();
      }
      toast("Yükleniyor (" + i + "/" + files.length + "): " + f.name + " …");
      var fd = new FormData();
      fd.append("file", f);
      api("/papers/upload", { method: "POST", body: fd })
        .then(function (resp) {
          // skipped=1 → sunucu birebir aynı dosyayı zaten var diye atladı (dedup).
          if (resp && resp.skipped) dup++;
          else ok++;
        })
        .catch(function () {
          fail++;
        })
        .finally(next);
    }

    function done() {
      var msg =
        ok +
        " PDF aktarıldı" +
        (dup ? ", " + dup + " zaten vardı (atlandı)" : "") +
        (fail ? ", " + fail + " hata" : "") +
        ". İndeksleniyor…";
      toast(msg);
      api("/papers")
        .then(function (data) {
          var prevCount = (data.papers || data || []).length;
          pollPapersUntilGrown(prevCount, 30);
        })
        .catch(function () { pollPapersUntilGrown(0, 30); });
    }

    function pollPapersUntilGrown(prevCount, attempts) {
      if (attempts <= 0) { loadPapers(); refreshStatus(); return; }
      setTimeout(function () {
        api("/papers")
          .then(function (data) {
            var list = data.papers || data || [];
            if (list.length > prevCount) {
              loadPapers();
              refreshStatus();
              toast("İndeksleme tamamlandı, makaleler güncellendi.");
            } else {
              pollPapersUntilGrown(prevCount, attempts - 1);
            }
          })
          .catch(function () { pollPapersUntilGrown(prevCount, attempts - 1); });
      }, 4000);
    }

    next();
  }

  // ---------- backtest ----------
  var btForm = document.getElementById("btForm");
  btForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var n = parseInt(document.getElementById("nBars").value, 10) || 2000;
    var seed = parseInt(document.getElementById("seed").value, 10) || 42;
    var btn = document.getElementById("btBtn");
    var res = document.getElementById("btResult");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>ÇALIŞIYOR';
    res.className = "result";
    res.innerHTML = '<div class="result-section"><span class="spinner"></span> backtest…</div>';

    api("/backtest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ use_synthetic: true, n_bars: n, seed: seed }),
    })
      .then(function (data) {
        renderBacktest(res, data);
        loadBacktestHistory();
      })
      .catch(function (err) {
        res.innerHTML =
          '<div class="result-section result-body">Hata: ' + esc(err.message) + "</div>";
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = "SENTETİK ÇALIŞTIR →";
      });
  });

  // ---------- backtest: gerçek veri (CSV) ----------
  var csvZone = document.getElementById("csvZone");
  var csvInput = document.getElementById("csvInput");
  if (csvZone && csvInput) {
    document.getElementById("csvBrowse").addEventListener("click", function (e) {
      e.stopPropagation();
      csvInput.click();
    });
    csvZone.addEventListener("click", function () {
      csvInput.click();
    });
    csvZone.addEventListener("dragover", function (e) {
      e.preventDefault();
      csvZone.classList.add("drag");
    });
    csvZone.addEventListener("dragleave", function () {
      csvZone.classList.remove("drag");
    });
    csvZone.addEventListener("drop", function (e) {
      e.preventDefault();
      csvZone.classList.remove("drag");
      if (e.dataTransfer.files && e.dataTransfer.files.length) {
        runCsvBacktest(e.dataTransfer.files[0]);
      }
    });
    csvInput.addEventListener("change", function () {
      if (csvInput.files && csvInput.files.length) runCsvBacktest(csvInput.files[0]);
    });
  }

  function runCsvBacktest(file) {
    if (!file.name.toLowerCase().endsWith(".csv")) {
      toast("Yalnız .csv kabul edilir.", true);
      return;
    }
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
      toast("Dosya " + MAX_UPLOAD_MB + " MB sınırını aşıyor.", true);
      return;
    }
    var res = document.getElementById("btResult");
    res.className = "result";
    res.innerHTML =
      '<div class="result-section"><span class="spinner"></span> gerçek veri backtest: ' +
      esc(file.name) +
      " …</div>";
    var fd = new FormData();
    fd.append("file", file);
    api("/backtest/csv", { method: "POST", body: fd })
      .then(function (data) {
        renderBacktest(res, data);
        loadBacktestHistory();
      })
      .catch(function (err) {
        res.innerHTML =
          '<div class="result-section result-body">Hata: ' + esc(err.message) + "</div>";
      });
  }

  function renderBacktest(res, data) {
    var m = data.metrics || {};
    var order = [
      ["n_trades", "işlem"],
      ["total_return_pct", "getiri %"],
      ["sharpe", "sharpe"],
      ["sortino", "sortino"],
      ["max_drawdown_pct", "max dd %"],
      ["profit_factor", "profit factor"],
      ["win_rate_pct", "win %"],
    ];
    var cells = order
      .map(function (pair) {
        var key = pair[0];
        if (!(key in m)) return "";
        var val = m[key];
        var cls = "";
        if (typeof val === "number") {
          if (key.indexOf("return") >= 0 || key === "sharpe" || key === "sortino") {
            cls = val > 0 ? "pos" : val < 0 ? "neg" : "";
          }
          if (key === "max_drawdown_pct") cls = "neg";
          val = Number(val).toFixed(key === "n_trades" ? 0 : 4);
        }
        return (
          '<div class="metric"><div class="k">' +
          esc(pair[1]) +
          '</div><div class="v ' +
          cls +
          '">' +
          esc(val) +
          "</div></div>"
        );
      })
      .join("");

    var v = data.verdict || "inconclusive";
    var vClass = "verdict-" + v;
    var vLabel = { pass: "GEÇTİ", fail: "BAŞARISIZ", inconclusive: "SONUÇSUZ" }[v] || v;
    var reasons = (data.reasons || [])
      .map(function (r) {
        return "<li>" + esc(r) + "</li>";
      })
      .join("");

    res.innerHTML =
      '<div class="result-section"><div class="result-label">strateji</div>' +
      '<div class="result-body">' +
      esc(data.strategy_name) +
      (data.data_source
        ? '  <span class="muted small">· veri: ' +
          esc(data.data_source) +
          (data.n_bars ? " (" + data.n_bars + " bar)" : "") +
          "</span>"
        : "") +
      (data.backtest_id ? '  <span class="muted small">(' + esc(data.backtest_id) + ")</span>" : "") +
      "</div></div>" +
      '<div class="result-section"><div class="result-label">metrikler</div>' +
      '<div class="metrics-grid">' +
      cells +
      "</div></div>" +
      '<div class="result-section"><div class="verdict ' +
      vClass +
      '"><h4>YARGI: ' +
      vLabel +
      "</h4><ul>" +
      reasons +
      "</ul></div></div>";
  }

  // ---------- trader beyin ----------
  function loadTraderBrain() {
    loadFormulas();
    loadResearchSessions();
  }

  function loadFormulas() {
    api("/research/formulas", { method: "GET" })
      .then(function (formulas) {
        var el = document.getElementById("formulasList");
        if (!el) return;
        if (!formulas.length) {
          el.innerHTML = '<div class="empty muted small">Formül bulunamadı — "FORMÜL ÇIKAR" butonuna bas.</div>';
          return;
        }
        var byCat = {};
        formulas.forEach(function (f) {
          var cat = f.category || "other";
          if (!byCat[cat]) byCat[cat] = [];
          byCat[cat].push(f);
        });
        var html = "";
        Object.keys(byCat).sort().forEach(function (cat) {
          html += '<div class="formula-cat"><span class="formula-cat-label">' + esc(cat.toUpperCase()) + "</span>";
          byCat[cat].forEach(function (f) {
            html += '<span class="formula-chip" title="' + esc(f.description || "") + '">' + esc(f.name) + "</span>";
          });
          html += "</div>";
        });
        el.innerHTML = html;
      })
      .catch(function () {});
  }

  var extractFormulasBtn = document.getElementById("extractFormulasBtn");
  if (extractFormulasBtn) {
    extractFormulasBtn.addEventListener("click", function () {
      extractFormulasBtn.disabled = true;
      extractFormulasBtn.innerHTML = '<span class="spinner"></span>ÇIKARILIYOR…';
      var res = document.getElementById("extractResult");
      res.className = "result";
      res.innerHTML = '<div class="result-section"><span class="spinner"></span> LLM formülleri çıkarıyor (~dakikalar)…</div>';
      api("/research/extract", { method: "POST" })
        .then(function (data) {
          toast(data.message);
          res.innerHTML = '<div class="result-section result-body">' + esc(data.message) + "</div>";
          loadFormulas();
        })
        .catch(function (err) {
          toast(err.message, true);
          res.innerHTML = '<div class="result-section result-body">Hata: ' + esc(err.message) + "</div>";
        })
        .finally(function () {
          extractFormulasBtn.disabled = false;
          extractFormulasBtn.textContent = "⚗ FORMÜL ÇIKAR";
        });
    });
  }

  var runResearchBtn = document.getElementById("runResearchBtn");
  if (runResearchBtn) {
    runResearchBtn.addEventListener("click", function () {
      var q = (document.getElementById("researchQuestion").value || "").trim();
      if (q.length < 10) { toast("Soru çok kısa (min 10 karakter).", true); return; }
      var maxIter = parseInt(document.getElementById("researchIter").value, 10) || 2;
      runResearchBtn.disabled = true;
      runResearchBtn.innerHTML = '<span class="spinner"></span>ARAŞTIRILYOR…';
      var res = document.getElementById("researchResult");
      res.className = "result";
      res.innerHTML = '<div class="result-section"><span class="spinner"></span> Sentezleniyor, backtest ediliyor… (her iterasyon ~2 dk)</div>';
      api("/research/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, max_iterations: maxIter }),
      })
        .then(function (data) {
          res.innerHTML = renderResearchResult(data);
          loadResearchSessions();
        })
        .catch(function (err) {
          res.innerHTML = '<div class="result-section result-body">Hata: ' + esc(err.message) + "</div>";
        })
        .finally(function () {
          runResearchBtn.disabled = false;
          runResearchBtn.textContent = "🧠 ARAŞTIR →";
        });
    });
  }

  function renderResearchResult(data) {
    var vClass = "verdict-" + (data.final_verdict || "inconclusive");
    var vLabel = { pass: "YAKINSADI ✓", fail: "BAŞARISIZ", inconclusive: "SONUÇSUZ" }[data.final_verdict] || data.final_verdict;
    var iters = (data.iterations || []).map(function (it) {
      var ivClass = "verdict-" + it.verdict;
      var m = it.metrics || {};
      var metHtml =
        '<div class="metric"><div class="k">getiri%</div><div class="v">' + (m.total_return_pct != null ? Number(m.total_return_pct).toFixed(3) : "—") + "</div></div>" +
        '<div class="metric"><div class="k">sharpe</div><div class="v">' + (m.sharpe != null ? Number(m.sharpe).toFixed(3) : "—") + "</div></div>" +
        '<div class="metric"><div class="k">işlem</div><div class="v">' + (m.n_trades || 0) + "</div></div>";
      return (
        '<div class="research-iter">' +
        '<div class="research-iter-head">' +
        '<span class="research-iter-num">İter ' + it.iteration + "</span>" +
        '<span class="research-ind-name">' + esc(it.indicator_name) + "</span>" +
        '<span class="verdict ' + ivClass + ' hist-verdict">' + it.verdict.toUpperCase() + "</span>" +
        "</div>" +
        '<div class="metrics-grid">' + metHtml + "</div>" +
        (it.reflection ? '<div class="research-reflection muted small">💭 ' + esc(it.reflection.slice(0, 200)) + "</div>" : "") +
        (it.improvement_notes ? '<div class="research-improvement muted small">→ ' + esc(it.improvement_notes) + "</div>" : "") +
        "</div>"
      );
    }).join("");
    return (
      '<div class="result-section"><div class="verdict ' + vClass + '"><b>' + vLabel + "</b></div></div>" +
      '<div class="result-section">' + iters + "</div>"
    );
  }

  function loadResearchSessions() {
    var el = document.getElementById("sessionsList");
    if (!el) return;
    api("/research/sessions", { method: "GET" })
      .then(function (rows) {
        if (!rows.length) {
          el.innerHTML = '<div class="empty">Henüz araştırma oturumu yok.</div>';
          return;
        }
        var vLabels = { pass: "✓ BAŞARILI", fail: "✗ BAŞARISIZ", inconclusive: "~ SONUÇSUZ" };
        var passed = rows.filter(function(r) { return r.verdict === "pass"; }).length;
        var failed = rows.filter(function(r) { return r.verdict === "fail"; }).length;
        var pending = rows.filter(function(r) { return !r.verdict; }).length;
        var summary = '<div class="sessions-summary">' +
          '<span class="verdict verdict-pass sess-count">✓ ' + passed + ' başarılı</span>' +
          '<span class="verdict verdict-fail sess-count">✗ ' + failed + ' başarısız</span>' +
          (pending ? '<span class="verdict verdict-inconclusive sess-count">~ ' + pending + ' bekliyor</span>' : '') +
          '</div>';
        el.innerHTML = summary + rows.map(function (r) {
          var vKey = r.verdict || "pending";
          var vClass = "verdict-" + (r.verdict || "inconclusive");
          var vLabel = vLabels[r.verdict] || "⏳ test bekleniyor";
          return (
            '<div class="hist-row">' +
            '<div class="hist-head">' +
            '<span class="hist-name">' + esc((r.indicator_name || "—")) + "</span>" +
            '<span class="muted small">iter ' + r.iteration + "</span>" +
            '<span class="verdict ' + vClass + ' hist-verdict">' + vLabel + "</span>" +
            '<span class="muted small">' + esc((r.created_at || "").slice(0, 10)) + "</span>" +
            "</div>" +
            '<div class="muted small">' + esc((r.question || "").slice(0, 80)) + "</div>" +
            "</div>"
          );
        }).join("");
      })
      .catch(function () {});
  }

  var refreshSessions = document.getElementById("refreshSessions");
  if (refreshSessions) refreshSessions.addEventListener("click", loadResearchSessions);

  var buildChainBtn = document.getElementById("buildChainBtn");
  if (buildChainBtn) {
    buildChainBtn.addEventListener("click", function () {
      var onlySuccessful = document.getElementById("onlySuccessful").checked;
      buildChainBtn.disabled = true;
      buildChainBtn.innerHTML = '<span class="spinner"></span>OLUŞTURULUYOR…';
      var res = document.getElementById("chainResult");
      res.className = "result";
      res.innerHTML = '<div class="result-section"><span class="spinner"></span></div>';
      api("/research/chain-dataset?only_successful=" + onlySuccessful, { method: "POST" })
        .then(function (data) {
          toast(data.n_records + " zincir kaydı üretildi.");
          res.innerHTML =
            '<div class="result-section result-body">' +
            data.n_records + " kayıt · hash: " + esc(data.content_hash) +
            "</div>";
        })
        .catch(function (err) {
          toast(err.message, true);
          res.innerHTML = '<div class="result-section result-body">Hata: ' + esc(err.message) + "</div>";
        })
        .finally(function () {
          buildChainBtn.disabled = false;
          buildChainBtn.textContent = "⚡ ZİNCİR DATASET OLUŞTUR";
        });
    });
  }

  // ---------- sentez makaleleri ----------
  function loadSynthPapers() {
    var list = document.getElementById("synthPapersList");
    if (!list) return;
    api("/synthesis/reports", { method: "GET" })
      .then(function (d) {
        var reports = (d && d.reports) || [];
        if (!reports.length) {
          list.innerHTML =
            '<p class="muted small">Henüz sentez makalesi yok — önce Agentic Araştırma çalıştır, sonra ÜRET.</p>';
          return;
        }
        list.innerHTML = reports
          .map(function (r) {
            return (
              '<div class="session-item">' +
              '<a href="/api/synthesis/reports/' + encodeURIComponent(r.name) +
              '" download>📄 ' + esc(r.name) + "</a>" +
              '<span class="muted small"> · ' + r.size_kb + " KB · " + esc(r.modified) + "</span>" +
              "</div>"
            );
          })
          .join("");
      })
      .catch(function () {});
  }
  var genSynthBtn = document.getElementById("genSynthPaperBtn");
  if (genSynthBtn) {
    genSynthBtn.addEventListener("click", function () {
      genSynthBtn.disabled = true;
      genSynthBtn.innerHTML = '<span class="spinner"></span>ÜRETİLİYOR…';
      var res = document.getElementById("synthPaperResult");
      res.className = "result";
      api("/synthesis/reports/generate", { method: "POST" })
        .then(function (d) {
          if (d.ok) {
            toast("Sentez makalesi üretildi: " + d.name);
            res.innerHTML =
              '<div class="result-section result-body">✓ ' + esc(d.name) + " üretildi.</div>";
            loadSynthPapers();
          } else {
            res.innerHTML =
              '<div class="result-section result-body">' + esc(d.message || "Üretilemedi") + "</div>";
          }
        })
        .catch(function (err) {
          toast(err.message, true);
          res.innerHTML =
            '<div class="result-section result-body">Hata: ' + esc(err.message) + "</div>";
        })
        .finally(function () {
          genSynthBtn.disabled = false;
          genSynthBtn.textContent = "📄 SENTEZ MAKALESİ ÜRET";
        });
    });
  }
  var refreshSynthBtn = document.getElementById("refreshSynthPapers");
  if (refreshSynthBtn) refreshSynthBtn.addEventListener("click", loadSynthPapers);
  loadSynthPapers();

  // ---------- model değerlendirme ----------
  function loadEvalSets() {
    var sel = document.getElementById("evalSetSelect");
    if (!sel) return;
    api("/eval/sets", { method: "GET" })
      .then(function (sets) {
        while (sel.options.length > 0) sel.remove(0);
        if (!sets.length) {
          var opt = document.createElement("option");
          opt.value = "";
          opt.textContent = "Eval seti bulunamadı";
          sel.appendChild(opt);
          return;
        }
        sets.forEach(function (s) {
          var opt = document.createElement("option");
          opt.value = s.name;
          opt.textContent = s.name + " (" + s.n_items + " soru)";
          sel.appendChild(opt);
        });
      })
      .catch(function () {});
  }

  var runEvalBtn = document.getElementById("runEvalBtn");
  if (runEvalBtn) {
    runEvalBtn.addEventListener("click", function () {
      var evalSet = document.getElementById("evalSetSelect").value;
      var adapterV = document.getElementById("evalAdapterSelect").value || null;
      if (!evalSet) { toast("Eval seti seç.", true); return; }
      runEvalBtn.disabled = true;
      runEvalBtn.innerHTML = '<span class="spinner"></span>ÇALIŞIYOR';
      var res = document.getElementById("evalResult");
      res.className = "result";
      res.innerHTML = '<div class="result-section"><span class="spinner"></span> LLM yanıtları alınıyor…</div>';
      api("/eval/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ eval_set: evalSet, adapter_version: adapterV }),
      })
        .then(function (data) {
          renderEvalResult(res, data);
        })
        .catch(function (err) {
          res.innerHTML = '<div class="result-section result-body">Hata: ' + esc(err.message) + "</div>";
        })
        .finally(function () {
          runEvalBtn.disabled = false;
          runEvalBtn.textContent = "DEĞERLENDİR →";
        });
    });
  }

  function renderEvalResult(res, data) {
    var scorePct = Math.round(data.score * 100);
    var scoreClass = scorePct >= 80 ? "pos" : scorePct >= 60 ? "" : "neg";
    var rows = (data.rows || []).map(function (r) {
      var flagHtml = r.flags.length
        ? r.flags.map(function (f) { return '<span class="eval-flag">' + esc(f) + "</span>"; }).join(" ")
        : '<span class="muted small">temiz</span>';
      return (
        '<div class="eval-row">' +
        '<div class="eval-q"><b>S:</b> ' + esc(r.question) + "</div>" +
        '<div class="eval-a"><b>C:</b> ' + esc(r.answer.slice(0, 200)) + (r.answer.length > 200 ? "…" : "") + "</div>" +
        '<div class="eval-flags">' + flagHtml + "</div>" +
        "</div>"
      );
    }).join("");
    res.innerHTML =
      '<div class="result-section"><div class="result-label">özet</div>' +
      '<div class="metrics-grid">' +
      '<div class="metric"><div class="k">skor</div><div class="v ' + scoreClass + '">' + scorePct + '%</div></div>' +
      '<div class="metric"><div class="k">soru</div><div class="v">' + data.n_items + "</div></div>" +
      '<div class="metric"><div class="k">bayrak</div><div class="v' + (data.total_flags > 0 ? " neg" : " pos") + '">' + data.total_flags + "</div></div>" +
      "</div>" +
      (data.adapter_version ? '<div class="muted small">adapter: ' + esc(data.adapter_version) + "</div>" : "") +
      "</div>" +
      '<div class="result-section"><div class="result-label">sorular</div>' +
      '<div class="eval-rows">' + rows + "</div></div>";
  }

  // ---------- backtest geçmişi ----------
  function loadBacktestHistory() {
    var el = document.getElementById("btHistory");
    if (!el) return;
    el.innerHTML = '<div class="empty"><span class="spinner"></span> yükleniyor…</div>';
    api("/backtests?limit=30", { method: "GET" })
      .then(function (data) {
        var recs = data.records || [];
        if (!recs.length) {
          el.innerHTML = '<div class="empty">Henüz kayıtlı backtest yok.</div>';
          return;
        }
        el.innerHTML = recs
          .map(function (r) {
            var v = r.verdict || "inconclusive";
            var vClass = "verdict-" + v;
            var vLabel = { pass: "GEÇTİ", fail: "BAŞARISIZ", inconclusive: "SONUÇSUZ" }[v] || v;
            var ret = r.total_return_pct != null ? Number(r.total_return_pct).toFixed(3) : "—";
            var sh = r.sharpe != null ? Number(r.sharpe).toFixed(3) : "—";
            var dd = r.max_drawdown_pct != null ? Number(r.max_drawdown_pct).toFixed(3) : "—";
            var wr = r.win_rate_pct != null ? Number(r.win_rate_pct).toFixed(1) : "—";
            return (
              '<div class="hist-row">' +
              '<div class="hist-head">' +
              '<span class="hist-name">' + esc(r.strategy_name) + "</span>" +
              (r.market ? '<span class="muted small">' + esc(r.market) + (r.timeframe ? "/" + esc(r.timeframe) : "") + "</span>" : "") +
              '<span class="verdict ' + vClass + ' hist-verdict">' + vLabel + "</span>" +
              '<span class="muted small">' + esc((r.created_at || "").slice(0, 10)) + "</span>" +
              "</div>" +
              '<div class="metrics-grid">' +
              '<div class="metric"><div class="k">getiri%</div><div class="v' + (r.total_return_pct > 0 ? " pos" : r.total_return_pct < 0 ? " neg" : "") + '">' + esc(ret) + "</div></div>" +
              '<div class="metric"><div class="k">sharpe</div><div class="v' + (r.sharpe > 0 ? " pos" : r.sharpe < 0 ? " neg" : "") + '">' + esc(sh) + "</div></div>" +
              '<div class="metric"><div class="k">maxDD%</div><div class="v neg">' + esc(dd) + "</div></div>" +
              '<div class="metric"><div class="k">win%</div><div class="v">' + esc(wr) + "</div></div>" +
              '<div class="metric"><div class="k">işlem</div><div class="v">' + esc(r.n_trades) + "</div></div>" +
              "</div>" +
              (r.notes ? '<div class="hist-notes muted small">' + esc(r.notes) + "</div>" : "") +
              '<div class="hist-actions">' +
              '<button class="btn btn-pine" data-btid="' + esc(r.backtest_id) + '" title="Pine Script\'i göster ve kopyala">🌲 Pine Kopyala</button>' +
              '<button class="btn btn-risk" data-btid="' + esc(r.backtest_id) + '" title="Kelly + drawdown risk analizi">⚖ Risk Analizi</button>' +
              '<button class="btn btn-pkg" data-btid="' + esc(r.backtest_id) + '" data-stratname="' + esc(r.strategy_name) + '" title=".achpkg paketini indir">⬇ .achpkg</button>' +
              "</div>" +
              "</div>"
            );
          })
          .join("");

        el.querySelectorAll(".btn-pine").forEach(function (b) {
          b.addEventListener("click", function () { openPineModal(b.getAttribute("data-btid")); });
        });
        el.querySelectorAll(".btn-risk").forEach(function (b) {
          b.addEventListener("click", function () { openRiskModal(b.getAttribute("data-btid")); });
        });
        el.querySelectorAll(".btn-pkg").forEach(function (b) {
          b.addEventListener("click", function () {
            downloadAchpkg(b.getAttribute("data-btid"), b.getAttribute("data-stratname"));
          });
        });
      })
      .catch(function (err) {
        el.innerHTML = '<div class="empty">Hata: ' + esc(err.message) + "</div>";
      });
  }

  function downloadAchpkg(btId, stratName) {
    toast(".achpkg hazırlanıyor…");
    fetch("/api/backtest/" + btId + "/download-pkg", { headers: authHeaders() })
      .then(function (r) {
        if (r.status === 401) { toast("Yetkisiz — API token gerekli.", true); throw new Error("unauthorized"); }
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.blob();
      })
      .then(function (blob) {
        var safeName = stratName.replace(/[^\w\-]/g, "_") || btId;
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = safeName + ".achpkg";
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        toast(".achpkg indirildi ✓");
      })
      .catch(function (err) { toast("İndirme hatası: " + esc(err.message || "Bilinmeyen hata"), true); });
  }

  // ---------- Pine Script modal ----------
  var pineModal = null;

  function openPineModal(btId) {
    if (!pineModal) {
      pineModal = document.createElement("div");
      pineModal.id = "pineModal";
      pineModal.className = "modal";
      pineModal.innerHTML =
        '<div class="modal-box" style="max-width:700px">' +
        '<button class="modal-close" id="pineClose">✕</button>' +
        '<div id="pineBody"></div>' +
        "</div>";
      document.body.appendChild(pineModal);
      document.getElementById("pineClose").addEventListener("click", function () {
        pineModal.className = "modal hidden";
      });
    }
    var body = document.getElementById("pineBody");
    body.innerHTML = '<div class="result-section"><span class="spinner"></span> yükleniyor…</div>';
    pineModal.className = "modal";

    api("/backtest/" + btId + "/pine", { method: "GET" })
      .then(function (d) {
        body.innerHTML =
          '<div class="result-section">' +
          '<div class="result-label">strateji</div>' +
          '<b>' + esc(d.strategy_name) + '</b> · ' + esc(d.market) + '/' + esc(d.timeframe) +
          '</div>' +
          '<div class="result-section">' +
          '<div class="result-label" style="display:flex;justify-content:space-between">' +
          '<span>Pine Script v5</span>' +
          '<button class="btn" id="copyPineBtn">📋 Panoya Kopyala</button>' +
          '</div>' +
          '<pre class="pine-code" id="pineCodePre" style="white-space:pre-wrap;font-size:12px;overflow:auto;max-height:400px">' +
          esc(d.pine_code) + '</pre>' +
          '</div>' +
          '<p class="muted small" style="margin-top:8px">' +
          'TradingView → Pine Script Editörü → Yeni → Kodu yapıştır → Derle → Strateji Tester' +
          '</p>';
        document.getElementById("copyPineBtn").addEventListener("click", function () {
          navigator.clipboard.writeText(d.pine_code).then(function () {
            toast("Pine Script panoya kopyalandı ✓");
          }).catch(function () {
            toast("Kopyalanamadı — kodu elle seç.", true);
          });
        });
      })
      .catch(function (err) {
        body.innerHTML = '<div class="result-section result-body">Hata: ' + esc(err.message) + "</div>";
      });
  }

  // ---------- Risk Analizi modal ----------
  var riskModalEl = document.getElementById("riskModal");
  if (riskModalEl) {
    document.getElementById("riskClose").addEventListener("click", function () {
      riskModalEl.className = "modal hidden";
    });
  }

  function openRiskModal(btId) {
    var body = document.getElementById("riskBody");
    body.innerHTML = '<div class="result-section"><span class="spinner"></span> risk hesaplanıyor…</div>';
    riskModalEl.className = "modal";

    api("/backtest/" + btId + "/risk?equity_usd=10000&max_dd_pct=-20&risk_pct=1&stop_pct=2", { method: "GET" })
      .then(function (d) {
        var k = d.kelly;
        var dd = d.drawdown_scale;
        var fr = d.fixed_risk;
        var warnHtml = d.warnings.length
          ? '<div class="result-section"><div class="result-label">⚠ uyarılar</div>' +
            d.warnings.map(function (w) { return '<div class="muted small">' + esc(w) + '</div>'; }).join("") +
            '</div>'
          : "";
        body.innerHTML =
          '<div class="result-section"><div class="result-label">strateji — risk analizi</div>' +
          '<b>' + esc(d.strategy_name) + '</b>  ·  ' + d.n_trades + ' işlem' +
          '</div>' +

          '<div class="result-section"><div class="result-label">Kelly Kriteri</div>' +
          '<div class="risk-grid">' +
          '<div class="risk-item"><div class="k">Kazanma oranı</div><div class="v">' + (k.win_rate*100).toFixed(1) + '%</div></div>' +
          '<div class="risk-item"><div class="k">Ort. kazanç</div><div class="v pos">' + (k.avg_win*100).toFixed(2) + '%</div></div>' +
          '<div class="risk-item"><div class="k">Ort. kayıp</div><div class="v neg">-' + (k.avg_loss*100).toFixed(2) + '%</div></div>' +
          '<div class="risk-item"><div class="k">Odds (b)</div><div class="v">' + k.odds.toFixed(2) + '</div></div>' +
          '<div class="risk-item"><div class="k">Tam Kelly</div><div class="v">' + (k.full_kelly*100).toFixed(1) + '%</div></div>' +
          '<div class="risk-item"><div class="k">Yarı Kelly</div><div class="v pos">' + (k.half_kelly*100).toFixed(1) + '%</div></div>' +
          '<div class="risk-item"><div class="k">Çeyrek Kelly</div><div class="v">' + (k.quarter_kelly*100).toFixed(1) + '%</div></div>' +
          '<div class="risk-item"><div class="k">Sınırlı Kelly</div><div class="v pos"><b>' + (k.capped_kelly*100).toFixed(1) + '%</b></div></div>' +
          '</div></div>' +

          '<div class="result-section"><div class="result-label">Drawdown Ölçekleme (eşik: ' + dd.max_allowed_pct + '%)</div>' +
          '<div class="risk-grid">' +
          '<div class="risk-item"><div class="k">Anlık DD</div><div class="v ' + (dd.in_drawdown_zone ? 'neg' : '') + '">' + dd.current_drawdown_pct.toFixed(1) + '%</div></div>' +
          '<div class="risk-item"><div class="k">Ölçek faktörü</div><div class="v ' + (dd.scale_factor < 1 ? 'neg' : 'pos') + '">' + (dd.scale_factor*100).toFixed(0) + '%</div></div>' +
          '<div class="risk-item"><div class="k">DD bölgesi</div><div class="v ' + (dd.in_drawdown_zone ? 'neg' : 'pos') + '">' + (dd.in_drawdown_zone ? '⚠ EVET' : '✓ HAYIR') + '</div></div>' +
          '</div></div>' +

          '<div class="result-section"><div class="result-label">Sabit Risk (sermaye: 10.000 $, risk: %1, stop: %2)</div>' +
          '<div class="risk-grid">' +
          '<div class="risk-item"><div class="k">Pozisyon %</div><div class="v">' + fr.position_size_pct.toFixed(1) + '%</div></div>' +
          '<div class="risk-item"><div class="k">Pozisyon $</div><div class="v"><b>' + fr.position_size_usd.toLocaleString() + ' $</b></div></div>' +
          '</div></div>' +

          warnHtml +
          '<div class="result-section"><div class="result-label">öneri</div>' +
          '<div class="result-body muted small">' + esc(d.recommendation) + '</div></div>' +
          (d.report_id
            ? '<div class="result-section"><span class="badge badge-ok">✓ Kaydedildi — ' + esc(d.report_id) + '</span></div>'
            : '');
        loadRiskReports();
      })
      .catch(function (err) {
        body.innerHTML = '<div class="result-section result-body">Hata: ' + esc(err.message) + '</div>';
      });
  }

  function loadRiskReports() {
    var list = document.getElementById("riskReportsList");
    if (!list) return;
    list.innerHTML = '<span class="spinner"></span>';
    api("/risk-reports?limit=20", { method: "GET" })
      .then(function (d) {
        if (!d.reports || d.reports.length === 0) {
          list.innerHTML = '<p class="muted small">Henüz kaydedilmiş risk raporu yok.</p>';
          return;
        }
        list.innerHTML = d.reports.map(function (r) {
          return '<div class="bt-card">' +
            '<div class="bt-meta">' +
            '<b>' + esc(r.strategy_name) + '</b>' +
            '<span class="muted small"> · ' + r.n_trades + ' işlem · ' + new Date(r.created_at).toLocaleString("tr-TR") + '</span>' +
            '</div>' +
            '<div class="risk-grid" style="margin-top:6px">' +
            '<div class="risk-item"><div class="k">Kazanma</div><div class="v">' + (r.win_rate * 100).toFixed(1) + '%</div></div>' +
            '<div class="risk-item"><div class="k">Yarı Kelly</div><div class="v pos">' + (r.half_kelly * 100).toFixed(1) + '%</div></div>' +
            '<div class="risk-item"><div class="k">Sınırlı Kelly</div><div class="v pos"><b>' + (r.capped_kelly * 100).toFixed(1) + '%</b></div></div>' +
            '<div class="risk-item"><div class="k">Ölçek</div><div class="v ' + (r.scale_factor < 1 ? 'neg' : 'pos') + '">' + (r.scale_factor * 100).toFixed(0) + '%</div></div>' +
            '<div class="risk-item"><div class="k">Pozisyon %</div><div class="v">' + r.position_size_pct.toFixed(1) + '%</div></div>' +
            '<div class="risk-item"><div class="k">Pozisyon $</div><div class="v">' + r.position_size_usd.toLocaleString() + ' $</div></div>' +
            '</div>' +
            '<div class="muted small" style="margin-top:4px">backtest: ' + esc(r.backtest_id) + '</div>' +
            '</div>';
        }).join("");
      })
      .catch(function () {
        list.innerHTML = '<p class="muted small">Risk raporları yüklenemedi.</p>';
      });
  }

  var refreshHistory = document.getElementById("refreshHistory");
  if (refreshHistory) {
    refreshHistory.addEventListener("click", loadBacktestHistory);
  }

  var refreshRiskReports = document.getElementById("refreshRiskReports");
  if (refreshRiskReports) {
    refreshRiskReports.addEventListener("click", loadRiskReports);
  }

  // ---------- özel strateji IR backtest ----------
  var customBtBtn = document.getElementById("customBtBtn");
  if (customBtBtn) {
    customBtBtn.addEventListener("click", function () {
      var raw = document.getElementById("customIR").value.trim();
      var n = parseInt(document.getElementById("customNBars").value, 10) || 2000;
      var seed = parseInt(document.getElementById("customSeed").value, 10) || 42;
      var strategyIr = null;
      if (raw) {
        try {
          strategyIr = JSON.parse(raw);
        } catch (e) {
          toast("Geçersiz JSON: " + e.message, true);
          return;
        }
      }
      var res = document.getElementById("btResult");
      customBtBtn.disabled = true;
      customBtBtn.innerHTML = '<span class="spinner"></span>ÇALIŞIYOR';
      res.className = "result";
      res.innerHTML = '<div class="result-section"><span class="spinner"></span> özel IR backtest…</div>';
      api("/backtest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ use_synthetic: true, n_bars: n, seed: seed, strategy_ir: strategyIr }),
      })
        .then(function (data) {
          renderBacktest(res, data);
          loadBacktestHistory();
        })
        .catch(function (err) {
          res.innerHTML = '<div class="result-section result-body">Hata: ' + esc(err.message) + "</div>";
        })
        .finally(function () {
          customBtBtn.disabled = false;
          customBtBtn.textContent = "ÖZEL IR ÇALIŞTIR →";
        });
    });
  }

  // ---------- kart onay ----------
  function loadPendingCards() {
    var container = document.getElementById("pending-cards-list");
    if (!container) return;
    container.innerHTML = '<div class="empty"><span class="spinner"></span> yükleniyor…</div>';
    api("/cards/pending", { method: "GET" })
      .then(function (data) {
        if (!data.cards || data.cards.length === 0) {
          container.innerHTML = '<p style="color:#94a3b8">Onay bekleyen kart yok.</p>';
        } else {
          var html = '<p style="color:#94a3b8;margin-bottom:8px">' + data.total + ' kart onay bekliyor</p>';
          data.cards.forEach(function (card) {
            var diffPct = Math.round(card.difficulty * 100);
            var stageLabel = card.stage || "—";
            html +=
              '<div style="border:1px solid var(--border);border-radius:var(--radius);padding:10px;margin-bottom:8px">' +
              '<div style="display:flex;justify-content:space-between;align-items:center">' +
              '<div>' +
              '<strong>' + esc(card.title || card.paper_id) + "</strong>" +
              '<span class="badge badge-warning" style="margin-left:8px">' + esc(stageLabel) + "</span>" +
              '<span class="badge badge-info" style="margin-left:4px">zorluk %' + diffPct + "</span>" +
              "</div>" +
              '<div style="display:flex;gap:8px">' +
              '<button class="btn btn-success btn-approve" data-card-id="' + esc(card.card_id) + '" style="padding:4px 12px">✓ Onayla</button>' +
              '<button class="btn btn-danger btn-reject" data-card-id="' + esc(card.card_id) + '" style="padding:4px 12px">✗ Reddet</button>' +
              "</div></div>" +
              '<p style="color:#94a3b8;margin-top:6px;font-size:12px">' + esc(card.main_claim || "") + "</p>" +
              '<small style="color:#94a3b8">kart: ' + esc(card.card_id) + " · model: " + esc(card.model) + "</small>" +
              "</div>";
          });
          container.innerHTML = html;
          container.querySelectorAll(".btn-approve").forEach(function (btn) {
            btn.addEventListener("click", function () {
              var cid = btn.getAttribute("data-card-id");
              api("/card/" + encodeURIComponent(cid) + "/approve", { method: "POST" })
                .then(function (d) {
                  toast(d.message);
                  loadPendingCards();
                })
                .catch(function (err) { toast(err.message, true); });
            });
          });
          container.querySelectorAll(".btn-reject").forEach(function (btn) {
            btn.addEventListener("click", function () {
              var cid = btn.getAttribute("data-card-id");
              api("/card/" + encodeURIComponent(cid) + "/reject", { method: "POST" })
                .then(function (d) {
                  toast(d.message);
                  loadPendingCards();
                })
                .catch(function (err) { toast(err.message, true); });
            });
          });
        }
        // Onaylananlar özeti
        api("/cards/approved", { method: "GET" })
          .then(function (d) {
            var el = document.getElementById("approved-cards-summary");
            if (el) el.textContent = d.total + " onaylı kart · LoRA'ya girebilir";
          })
          .catch(function () {});
      })
      .catch(function (err) {
        container.innerHTML = '<div class="empty">Hata: ' + esc(err.message) + "</div>";
      });
  }

  var btnLoadPending = document.getElementById("btn-load-pending");
  if (btnLoadPending) {
    btnLoadPending.addEventListener("click", loadPendingCards);
  }

  // ---------- sistem durumu ----------
  function loadSystemStatus() {
    var el = document.getElementById("systemStatusDisplay");
    if (!el) return;
    el.innerHTML = '<span class="spinner"></span> güncelleniyor…';
    api("/status", { method: "GET" })
      .then(function (s) {
        el.innerHTML =
          '<div class="metrics-grid" style="margin-top:8px">' +
          '<div class="metric"><div class="k">LLM model</div><div class="v">' + esc(s.llm_model) + '</div></div>' +
          '<div class="metric"><div class="k">Ollama</div><div class="v ' + (s.ollama_available ? "pos" : "neg") + '">' + (s.ollama_available ? "bağlı ✓" : "kapalı ✗") + '</div></div>' +
          '<div class="metric"><div class="k">Embed modu</div><div class="v">' + esc(s.embedding_mode) + '</div></div>' +
          '<div class="metric"><div class="k">Makale sayısı</div><div class="v">' + s.n_papers + '</div></div>' +
          '<div class="metric"><div class="k">Chunk sayısı</div><div class="v">' + s.n_chunks + '</div></div>' +
          '<div class="metric"><div class="k">Max yükleme</div><div class="v">' + s.max_upload_mb + ' MB</div></div>' +
          '</div>';
      })
      .catch(function () {
        el.innerHTML = '<span class="conn-err">Durum alınamadı.</span>';
      });
  }

  // ---------- token ----------
  var tokenInput = document.getElementById("tokenInput");
  if (tokenInput) tokenInput.value = getToken();
  var saveTokenBtn = document.getElementById("saveToken");
  if (saveTokenBtn) saveTokenBtn.addEventListener("click", function () {
    setToken(tokenInput ? tokenInput.value.trim() : "");
    toast("Token kaydedildi.");
    refreshStatus();
  });

  // ---------- auto-lora pipeline ----------
  var _STAGE_LABELS = {
    idle: 'Boşta', checking: 'Gate kontrol ediliyor…', gate_failed: 'Gate başarısız',
    ready_to_train: 'Gate geçti — Eğitim onayı bekleniyor', training: 'Eğitim sürüyor…',
    train_failed: 'Eğitim başarısız', evaluating: 'Eval çalışıyor…',
    eval_failed: 'Eval başarısız', eval_passed: 'Eval geçti — Production onayı bekleniyor',
    promoted: 'Production\'a terfi edildi ✓'
  };
  var _STAGE_COLORS = {
    idle: '#94a3b8', checking: '#facc15', gate_failed: '#f87171',
    ready_to_train: '#60a5fa', training: '#a78bfa', train_failed: '#f87171',
    evaluating: '#a78bfa', eval_failed: '#f87171', eval_passed: '#34d399', promoted: '#4ade80'
  };

  function renderAutoLoraStatus(d) {
    var label = _STAGE_LABELS[d.stage] || d.stage;
    var color = _STAGE_COLORS[d.stage] || '#94a3b8';
    var rows = [
      ['Durum', '<strong style="color:' + color + '">' + esc(label) + '</strong>'],
      ['Onaylı kart', esc(d.approved_cards_at_last_check) + ' / min ' + esc(d.min_eligible_cards)],
      ['Son kontrol', d.last_check ? esc(d.last_check.slice(0,16).replace('T',' ')) : '—'],
      ['Gate özeti', esc(d.gate_summary || '—')],
      ['Adapter', esc(d.adapter_id || '—')],
      ['Hata', esc(d.last_error || '—')]
    ];
    var html = '<table style="width:100%;border-collapse:collapse;font-size:12px">';
    rows.forEach(function(r) {
      html += '<tr><td style="padding:2px 10px 2px 0;color:#94a3b8;white-space:nowrap">' + r[0] + '</td><td>' + r[1] + '</td></tr>';
    });
    html += '</table>';
    var trainBtn = document.getElementById('autoLoraTrainBtn');
    var promoteBtn = document.getElementById('autoLoraPromoteBtn');
    var enableLabel = document.getElementById('autoLoraEnabledLabel');
    if (trainBtn) trainBtn.disabled = d.stage !== 'ready_to_train';
    if (promoteBtn) promoteBtn.disabled = d.stage !== 'eval_passed';
    if (enableLabel) {
      enableLabel.textContent = d.auto_enabled ? 'açık' : 'kapalı';
      enableLabel.className = 'badge ' + (d.auto_enabled ? 'badge-success' : 'badge-info');
    }
    return html;
  }

  function loadAutoLoraStatus() {
    var body = document.getElementById('autoLoraStatusBody');
    if (!body) return;
    api('/auto-lora/status', { method: 'GET' })  // api() = auth header + hata yönetimi
      .then(function(d) { body.innerHTML = renderAutoLoraStatus(d); })
      .catch(function() { body.innerHTML = '<span class="muted small">Durum alınamadı</span>'; });
  }

  function autoLoraMsg(text, ok) {
    var el = document.getElementById('autoLoraMsg');
    if (!el) return;
    el.textContent = text;
    el.className = 'result ' + (ok ? '' : 'error');
  }

  var autoLoraRefreshBtn = document.getElementById('autoLoraRefreshBtn');
  var autoLoraEnableBtn  = document.getElementById('autoLoraEnableBtn');
  var autoLoraDisableBtn = document.getElementById('autoLoraDisableBtn');
  var autoLoraCheckBtn   = document.getElementById('autoLoraCheckBtn');
  var autoLoraTrainBtn   = document.getElementById('autoLoraTrainBtn');
  var autoLoraPromoteBtn = document.getElementById('autoLoraPromoteBtn');
  var autoLoraResetBtn   = document.getElementById('autoLoraResetBtn');

  if (autoLoraRefreshBtn) autoLoraRefreshBtn.addEventListener('click', loadAutoLoraStatus);

  if (autoLoraEnableBtn) autoLoraEnableBtn.addEventListener('click', function() {
    api('/auto-lora/enable?enabled=true', { method: 'POST' })
      .then(function() { autoLoraMsg('Otomatik kontrol açıldı.', true); loadAutoLoraStatus(); })
      .catch(function(e) { autoLoraMsg('Bağlantı hatası: ' + e.message, false); });
  });
  if (autoLoraDisableBtn) autoLoraDisableBtn.addEventListener('click', function() {
    api('/auto-lora/enable?enabled=false', { method: 'POST' })
      .then(function() { autoLoraMsg('Otomatik kontrol kapatıldı.', true); loadAutoLoraStatus(); })
      .catch(function(e) { autoLoraMsg('Bağlantı hatası: ' + e.message, false); });
  });
  if (autoLoraCheckBtn) autoLoraCheckBtn.addEventListener('click', function() {
    autoLoraMsg('Gate 0-8 kontrol ediliyor…', true);
    api('/auto-lora/check', { method: 'POST' })
      .then(function(d) {
        autoLoraMsg(d.ok ? 'Gate geçti: ' + (d.summary||'') : 'Gate başarısız: ' + (d.reason||''), d.ok);
        loadAutoLoraStatus();
      }).catch(function(e) { autoLoraMsg('Bağlantı hatası: ' + e.message, false); });
  });
  if (autoLoraTrainBtn) autoLoraTrainBtn.addEventListener('click', function() {
    var nameEl = document.getElementById('autoLoraAdapterName') || document.getElementById('trAdapterName');
    var itersEl = document.getElementById('autoLoraIters') || document.getElementById('drIterations');
    var name = (nameEl && nameEl.value.trim()) || ('achilles_auto_' + Date.now());
    var iters = parseInt((itersEl && itersEl.value) || '300', 10);
    // Backend ile aynı kısıt (path-traversal/arg güvenliği) — erken, net geri bildirim.
    if (!/^[A-Za-z0-9_-]{1,64}$/.test(name)) {
      autoLoraMsg('Adapter adı yalnız harf, rakam, _ ve - içerebilir (en çok 64).', false); return;
    }
    if (iters < 50 || iters > 5000) { autoLoraMsg('İterasyon 50–5000 arasında olmalı.', false); return; }
    if (!confirm('Eğitim başlatılacak:\nAdapter: ' + name + '\nİterasyon: ' + iters + '\n\nOnaylıyor musun?')) return;
    autoLoraMsg('Eğitim başlatılıyor…', true);
    api('/auto-lora/train?adapter_name=' + encodeURIComponent(name) + '&iters=' + iters, { method: 'POST' })
      .then(function(d) {
        autoLoraMsg(d.ok ? '✓ Eğitim başladı: ' + esc(d.adapter_name) + ' (' + iters + ' iter)' : 'Hata: ' + (d.reason || 'bilinmiyor'), d.ok);
        loadAutoLoraStatus();
      }).catch(function(e) { autoLoraMsg('Bağlantı hatası: ' + e.message, false); });
  });
  if (autoLoraPromoteBtn) autoLoraPromoteBtn.addEventListener('click', function() {
    if (!confirm('Bu adapter production\'a terfi ettirilecek. Onaylıyor musun?')) return;
    api('/auto-lora/promote', { method: 'POST' })
      .then(function(d) {
        autoLoraMsg(d.ok ? 'Terfi edildi: ' + esc(d.adapter_id) : 'Hata: ' + (d.reason || 'bilinmiyor'), d.ok);
        loadAutoLoraStatus();
      }).catch(function(e) { autoLoraMsg('Bağlantı hatası: ' + e.message, false); });
  });
  if (autoLoraResetBtn) autoLoraResetBtn.addEventListener('click', function() {
    if (!confirm('Pipeline IDLE\'a sıfırlanacak. Devam?')) return;
    api('/auto-lora/reset', { method: 'POST' })
      .then(function() { autoLoraMsg('Sıfırlandı.', true); loadAutoLoraStatus(); })
      .catch(function(e) { autoLoraMsg('Bağlantı hatası: ' + e.message, false); });
  });

  loadAutoLoraStatus();

  // ---------- donanım profili + model önerisi ----------
  function renderHwProfile(profile, recs) {
    var loraBackend = profile.lora_backend || (profile.lora_supported ? 'mlx' : 'peft_cpu');
    var loraNote = loraBackend === 'mlx'
      ? '<span style="color:#4ade80">&#10003; LoRA egitimi destekleniyor (MLX - Apple Silicon, hizli)</span>'
      : loraBackend === 'peft_cuda'
        ? '<span style="color:#4ade80">&#10003; LoRA egitimi destekleniyor (CUDA GPU, hizli)</span>'
        : '<span style="color:#facc15">&#9888; LoRA egitimi CPU ile calisir (yavas ~2-4 saat) &mdash; Hizli egitim icin Egitim sekmesindeki "Colab Notebook Indir" dugmesini kullanin.</span>';
    var recsHtml = recs.recommended.length
      ? recs.recommended.map(function (r) {
          return (
            '<tr><td><strong>' + r.name + '</strong></td>' +
            '<td><code>' + r.ollama + '</code></td>' +
            '<td>' + r.confidence + '%</td></tr>'
          );
        }).join('')
      : '<tr><td colspan="3" class="muted">Öneri bulunamadı.</td></tr>';

    return (
      '<table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:10px">' +
      '<tr><td style="padding:3px 8px 3px 0"><strong>İşletim Sistemi</strong></td><td>' + profile.os + ' ' + profile.arch + '</td></tr>' +
      '<tr><td style="padding:3px 8px 3px 0"><strong>CPU</strong></td><td>' + profile.cpu + ' (' + profile.cores + ' çekirdek)</td></tr>' +
      '<tr><td style="padding:3px 8px 3px 0"><strong>RAM</strong></td><td>' + profile.ram_gb + ' GB</td></tr>' +
      '<tr><td style="padding:3px 8px 3px 0"><strong>GPU</strong></td><td>' + profile.gpu + '</td></tr>' +
      '</table>' +
      loraNote +
      '<h4 style="margin:12px 0 6px">Önerilen Modeller</h4>' +
      '<table style="width:100%;border-collapse:collapse;font-size:13px">' +
      '<thead><tr><th style="text-align:left;padding-bottom:4px">Model</th><th style="text-align:left">Ollama Komutu</th><th style="text-align:left">Uyum</th></tr></thead>' +
      '<tbody>' + recsHtml + '</tbody></table>'
    );
  }

  function loadHwProfile(targetEl) {
    Promise.all([
      fetch('/api/profile').then(function (r) { return r.json(); }),
      fetch('/api/recommend').then(function (r) { return r.json(); })
    ]).then(function (results) {
      targetEl.innerHTML = renderHwProfile(results[0], results[1]);
    }).catch(function () {
      targetEl.innerHTML = '<span class="muted small">Profil alınamadı.</span>';
    });
  }

  var hwProfileBody = document.getElementById('hwProfileBody');
  if (hwProfileBody) loadHwProfile(hwProfileBody);

  var setupModal = document.getElementById('setupModal');
  var setupModalBody = document.getElementById('setupModalBody');
  var setupModalClose = document.getElementById('setupModalClose');
  var setupModalDismiss = document.getElementById('setupModalDismiss');

  if (setupModal && !localStorage.getItem('achilles_setup_seen')) {
    loadHwProfile(setupModalBody);
    setupModal.classList.remove('hidden');
  }

  function closeSetupModal() {
    if (setupModal) setupModal.classList.add('hidden');
    localStorage.setItem('achilles_setup_seen', '1');
  }
  if (setupModalClose) setupModalClose.addEventListener('click', closeSetupModal);
  if (setupModalDismiss) setupModalDismiss.addEventListener('click', closeSetupModal);

  // ---------- 09 · ÖĞRENME dashboard ----------

  function _svgLinePath(points, xScale, yScale, viewW, viewH, padX, padY) {
    if (!points.length) return '';
    return points.map((p, i) => {
      const x = padX + p.x * xScale;
      const y = viewH - padY - p.y * yScale;
      return (i === 0 ? 'M' : 'L') + x.toFixed(1) + ' ' + y.toFixed(1);
    }).join(' ');
  }

  function renderLossCurve(curve) {
    const svg = document.getElementById('lrnLossSvg');
    if (!svg) return;
    if (!curve || !curve.length) {
      svg.innerHTML = '<text x="350" y="115" text-anchor="middle" fill="#666" font-size="13">Henüz eğitim verisi yok</text>';
      return;
    }
    const W = 700, H = 220, padX = 48, padY = 20;
    const iters = curve.map(d => d.iter);
    const trains = curve.map(d => d.train_loss);
    const vals = curve.filter(d => d.val_loss != null).map(d => d.val_loss);
    const maxIter = Math.max(...iters) || 1;
    const maxLoss = Math.max(...trains, ...vals, 0.01);
    const xS = (W - padX * 2) / maxIter;
    const yS = (H - padY * 2) / maxLoss;
    const trainPts = curve.map(d => ({ x: d.iter, y: d.train_loss }));
    const valPts = curve.filter(d => d.val_loss != null).map(d => ({ x: d.iter, y: d.val_loss }));
    const trainPath = _svgLinePath(trainPts, xS, yS, W, H, padX, padY);
    const valPath = _svgLinePath(valPts, xS, yS, W, H, padX, padY);
    // axis labels
    const yLabels = [0, maxLoss * 0.5, maxLoss].map(v => {
      const y = H - padY - v * yS;
      return `<text x="${padX - 4}" y="${y.toFixed(1)}" text-anchor="end" fill="#888" font-size="10">${v.toFixed(2)}</text>`;
    }).join('');
    const xLabels = [0, Math.round(maxIter / 2), maxIter].map(it => {
      const x = padX + it * xS;
      return `<text x="${x.toFixed(1)}" y="${H - 4}" text-anchor="middle" fill="#888" font-size="10">${it}</text>`;
    }).join('');
    svg.innerHTML = yLabels + xLabels +
      (trainPath ? `<path d="${trainPath}" stroke="#4af" stroke-width="1.8" fill="none"/>` : '') +
      (valPath   ? `<path d="${valPath}"   stroke="#fa4" stroke-width="1.8" fill="none" stroke-dasharray="4 2"/>` : '');
  }

  function renderCardGrowth(rows) {
    const svg = document.getElementById('lrnGrowthSvg');
    if (!svg) return;
    if (!rows || !rows.length) {
      svg.innerHTML = '<text x="350" y="95" text-anchor="middle" fill="#666" font-size="13">Henüz onaylı kart yok</text>';
      return;
    }
    const W = 700, H = 180, padX = 48, padY = 20;
    const maxCum = Math.max(...rows.map(r => r.cumulative), 1);
    const barW = Math.max(4, Math.floor((W - padX * 2) / rows.length) - 2);
    const xStep = (W - padX * 2) / rows.length;
    const yS = (H - padY * 2) / maxCum;
    const bars = rows.map((r, i) => {
      const bh = Math.max(2, r.cumulative * yS);
      const x = padX + i * xStep;
      const y = H - padY - bh;
      return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW}" height="${bh.toFixed(1)}" fill="#4af" opacity="0.7" rx="2"/>`;
    }).join('');
    const lastRow = rows[rows.length - 1];
    const topLabel = `<text x="${W - padX}" y="${padY}" text-anchor="end" fill="#4af" font-size="11">${lastRow.cumulative} toplam</text>`;
    svg.innerHTML = bars + topLabel;
  }

  function renderEvalTable(rows) {
    const el = document.getElementById('lrnEvalTable');
    if (!el) return;
    if (!rows || !rows.length) {
      el.innerHTML = '<span class="muted small">Henüz eval kaydı yok</span>';
      return;
    }
    const grouped = {};
    rows.forEach(r => {
      if (!grouped[r.adapter_name]) grouped[r.adapter_name] = [];
      grouped[r.adapter_name].push(r);
    });
    let html = '<table style="width:100%;border-collapse:collapse;font-size:.85rem"><thead><tr>' +
      '<th style="text-align:left;padding:.3rem .5rem;border-bottom:1px solid var(--border)">Adapter</th>' +
      '<th style="text-align:left;padding:.3rem .5rem;border-bottom:1px solid var(--border)">Eval Set</th>' +
      '<th style="text-align:right;padding:.3rem .5rem;border-bottom:1px solid var(--border)">Geçiş %</th>' +
      '<th style="text-align:right;padding:.3rem .5rem;border-bottom:1px solid var(--border)">Geçen/Toplam</th>' +
      '<th style="padding:.3rem .5rem;border-bottom:1px solid var(--border)">Tarih</th>' +
      '</tr></thead><tbody>';
    rows.slice().reverse().forEach(r => {
      const pct = (r.pass_rate * 100).toFixed(1);
      const color = r.pass_rate >= 0.5 ? '#4a4' : '#a44';
      html += `<tr>
        <td style="padding:.3rem .5rem;font-family:monospace">${esc(r.adapter_name)}</td>
        <td style="padding:.3rem .5rem">${esc(r.eval_set)}</td>
        <td style="text-align:right;padding:.3rem .5rem;color:${color}"><strong>${pct}%</strong></td>
        <td style="text-align:right;padding:.3rem .5rem">${r.passed_items || 0}/${r.total_items || 0}</td>
        <td style="padding:.3rem .5rem;color:#888;font-size:.75rem">${esc((r.scored_at||'').slice(0,10))}</td>
      </tr>`;
    });
    html += '</tbody></table>';
    el.innerHTML = html;
  }

  let _lrnRuns = [];

  async function loadLearningDashboard() {
    try {
      const [sum, evalData, runsData, growthData] = await Promise.all([
        api('/learning/summary', { method: 'GET' }),       // api() = auth header + hata
        api('/learning/eval-history', { method: 'GET' }),
        api('/learning/training-runs', { method: 'GET' }),
        api('/learning/card-growth', { method: 'GET' }),
      ]);
      document.getElementById('lrn-papers').textContent  = sum.n_papers   ?? '—';
      document.getElementById('lrn-chunks').textContent  = sum.n_chunks   ?? '—';
      document.getElementById('lrn-approved').textContent= sum.n_approved_cards ?? '—';
      document.getElementById('lrn-pending').textContent = sum.n_pending_cards  ?? '—';

      renderEvalTable(evalData.rows || []);

      _lrnRuns = runsData.runs || [];
      const sel = document.getElementById('lrnRunSelect');
      if (sel) {
        sel.innerHTML = _lrnRuns.length
          ? _lrnRuns.map((r, i) => `<option value="${i}">${esc(r.adapter_name)}</option>`).join('')
          : '<option value="">— yok —</option>';
        if (_lrnRuns.length) renderLossCurve(_lrnRuns[0].curve);
      }

      renderCardGrowth(growthData.rows || []);
    } catch (e) {
      console.error('learning dashboard yüklenemedi', e);
    }
  }

  const lrnRunSel = document.getElementById('lrnRunSelect');
  if (lrnRunSel) {
    lrnRunSel.addEventListener('change', () => {
      const i = parseInt(lrnRunSel.value, 10);
      if (_lrnRuns[i]) renderLossCurve(_lrnRuns[i].curve);
    });
  }

  const lrnRefreshBtn = document.getElementById('lrnRefreshBtn');
  if (lrnRefreshBtn) lrnRefreshBtn.addEventListener('click', loadLearningDashboard);

  // Auto-load when tab is clicked
  document.querySelectorAll('.tab[data-tab="learning"]').forEach(btn => {
    btn.addEventListener('click', loadLearningDashboard);
  });

  // ---------- egitim rozeti (ust bar) ----------
  // Uc durum: CANLI (nabizli) · HAZIR (tek tikla baslat) · YOK.
  // Gercek egitimi web'den VEYA detached/CLI'dan algilar (/api/training/live).
  var _trainStarting = false;

  function startTrainingFromBadge(examples) {
    if (_trainStarting) return;
    var msg =
      "LoRA eğitimi başlatılsın mı?\n\n" +
      examples + " örnek · ~1 epoch.\n" +
      "Uzun sürer (saatlerce); bilgisayar açık kalmalı.\n" +
      "Eğitim, web/terminal kapansa da arka planda sürer.";
    if (!window.confirm(msg)) return;
    _trainStarting = true;
    var stamp = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, "");
    api("/training/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ adapter_name: "achilles_auto_" + stamp, iterations: 0 }),
    })
      .then(function (d) {
        toast(d.message, !d.ok);
        refreshTrain();
      })
      .catch(function (e) {
        toast(e.message, true);
      })
      .finally(function () {
        _trainStarting = false;
      });
  }

  // Detached eğitimde SSE beslenmediği için EĞİTİM sekmesi ilerlemesini de
  // /api/training/live'dan aynala (sekme boş kalmasın).
  function mirrorTrainTab(t) {
    var section = document.getElementById("trainProgressSection");
    var bar = document.getElementById("trainProgressBar");
    var pctLbl = document.getElementById("trainPctLabel");
    var iterLbl = document.getElementById("trainIterLabel");
    var stateLbl = document.getElementById("trainStateLabel");
    if (section) section.style.display = "";
    if (bar) bar.style.width = (t.pct || 0) + "%";
    if (pctLbl) pctLbl.textContent = (t.pct || 0) + "%";
    if (iterLbl) iterLbl.textContent = (t.step || 0) + " / " + (t.total || 0) + " iter";
    if (stateLbl) {
      stateLbl.textContent = "eğitiliyor… (detached)";
      stateLbl.className = "badge badge-warn";
    }
    var meta = document.getElementById("trainMeta");
    if (meta && t.adapter) meta.textContent = "Adapter: " + t.adapter + "  ·  kaynak: detached";
    // Detached eğitimde SSE beslenmez → son log satırlarını çekip göster (boş kalmasın).
    var logEl = document.getElementById("trainLog");
    if (logEl) {
      api("/training/logs?lines=40", { method: "GET" })
        .then(function (d) {
          if (d && d.lines && d.lines.length) {
            logEl.textContent = d.lines.join("\n");
            logEl.scrollTop = logEl.scrollHeight;
          }
        })
        .catch(function () {});
    }
  }

  function refreshTrain() {
    var el = document.getElementById("trainBadge");
    if (!el) return;
    // Klavye/erişilebilirlik ipuçlarını her döngüde sıfırla (yalnız HAZIR iken aktif).
    function clearInteractive() {
      el.onclick = null;
      el.onkeydown = null;
      el.style.cursor = "";
      el.removeAttribute("role");
      el.removeAttribute("tabindex");
    }
    api("/training/live", { method: "GET" })
      .then(function (t) {
        clearInteractive();
        if (t && t.running) {
          el.className = "train-live"; // nabız atan nokta (CSS) + turuncu — CVD-safe
          var who = t.adapter ? (" " + t.adapter) : "";
          var eta = t.eta ? ("  ETA " + t.eta) : "";
          el.textContent = "EĞİTİM:" + who + " " + t.step + "/" + t.total + " (%" + t.pct + ")" + eta;
          el.title = "Eğitim çalışıyor (" + (t.source === "web" ? "web" : "detached/CLI") + ") — adapter: " + (t.adapter || "LoRA");
          mirrorTrainTab(t);
        } else if (t && t.ready) {
          el.className = "train-ready"; // teal + ▶ — tıklanabilir davet (CVD-safe)
          el.textContent = "▶ EĞİTİME HAZIR (" + t.ready_examples + " örnek) — BAŞLAT";
          el.title = "Tıkla / Enter → LoRA eğitimini başlat (onay sorulur). " + t.ready_label;
          el.style.cursor = "pointer";
          // Klavye erişimi: span'i buton gibi davranıştır (Tab + Enter/Space).
          el.setAttribute("role", "button");
          el.setAttribute("tabindex", "0");
          var start = function () { startTrainingFromBadge(t.ready_examples); };
          el.onclick = start;
          el.onkeydown = function (e) {
            if (e.key === "Enter" || e.key === " " || e.key === "Spacebar") {
              e.preventDefault();
              start();
            }
          };
        } else {
          el.className = "train-idle";
          el.textContent = "eğitim yok" + (t && t.ready_label ? " (" + t.ready_label + ")" : "");
          el.title = "Aktif LoRA eğitimi yok";
        }
      })
      .catch(function () {
        clearInteractive();
        el.className = "train-idle";
        el.textContent = "eğitim: —";
      });
  }

  // ---------- init ----------
  refreshStatus();
  setInterval(refreshStatus, 30000);
  refreshTrain();
  setInterval(refreshTrain, 15000);
})();
