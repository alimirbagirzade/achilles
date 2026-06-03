/* ACHILLES terminal — frontend logic (CSP-safe, harici dosya). */
(function () {
  "use strict";

  var TOKEN_KEY = "achilles_api_token";
  var MAX_UPLOAD_MB = 50; // /api/status'tan dinamik güncellenir
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
      if (name === "backtest") loadBacktestHistory();
      if (name === "training") loadTrainingStatus();
      if (name === "eval") loadEvalSets();
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

  // ---------- papers ----------
  var _allPapers = [];

  function loadPapers() {
    var list = document.getElementById("papersList");
    list.innerHTML = '<div class="empty"><span class="spinner"></span> yükleniyor…</div>';
    api("/papers", { method: "GET" })
      .then(function (papers) {
        _allPapers = papers || [];
        renderPapers();
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
      document.getElementById("hypBtBtn").addEventListener("click", function () {
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
    var el = document.getElementById("trainingStatus");
    el.innerHTML = '<span class="spinner"></span> yükleniyor…';
    api("/training/status", { method: "GET" })
      .then(function (data) {
        el.innerHTML =
          '<div class="training-stat">' +
          '<span class="kc-label">Eğitim örnekleri</span> ' +
          '<strong>' + data.n_examples + '</strong>' +
          '</div>';
        renderAdapters(data.adapters || []);
        loadExamples();
      })
      .catch(function (err) {
        el.innerHTML = '<span class="conn-err">Hata: ' + esc(err.message) + "</span>";
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

  var dryRunForm = document.getElementById("dryRunForm");
  if (dryRunForm) {
    dryRunForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var btn = document.getElementById("dryRunBtn");
      var res = document.getElementById("dryRunResult");
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span>HAZIRLANYOR';
      res.className = "result";
      res.innerHTML = '<div class="result-section"><span class="spinner"></span></div>';
      var payload = {
        base_model: document.getElementById("drBaseModel").value.trim(),
        iterations: parseInt(document.getElementById("drIterations").value, 10) || 600,
        batch_size: parseInt(document.getElementById("drBatch").value, 10) || 4,
        num_layers: parseInt(document.getElementById("drLayers").value, 10) || 16,
        learning_rate: 1e-4,
      };
      api("/training/dry-run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
        .then(function (data) {
          res.innerHTML =
            '<div class="result-section"><div class="result-label">komut</div>' +
            '<pre class="dry-run-cmd">' + esc(data.command) + "</pre></div>" +
            '<div class="result-section result-body">' +
            esc(data.message) +
            " (" + data.n_train + " eğitim / " + data.n_valid + " doğrulama)" +
            "</div>";
        })
        .catch(function (err) {
          toast(err.message, true);
          res.innerHTML = '<div class="result-section result-body">Hata: ' + esc(err.message) + "</div>";
        })
        .finally(function () {
          btn.disabled = false;
          btn.textContent = "KOMUT ÖNIZLE →";
        });
    });
  }

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
      fail = 0;
    function next() {
      if (i >= files.length) {
        toast(ok + " PDF yüklendi" + (fail ? ", " + fail + " atlandı/hata" : "") + ".");
        loadPapers();
        refreshStatus();
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
        .then(function () {
          ok++;
        })
        .catch(function () {
          fail++;
        })
        .finally(next);
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
              "</div>"
            );
          })
          .join("");
      })
      .catch(function (err) {
        el.innerHTML = '<div class="empty">Hata: ' + esc(err.message) + "</div>";
      });
  }

  var refreshHistory = document.getElementById("refreshHistory");
  if (refreshHistory) {
    refreshHistory.addEventListener("click", loadBacktestHistory);
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

  // ---------- token ----------
  var tokenInput = document.getElementById("tokenInput");
  tokenInput.value = getToken();
  document.getElementById("saveToken").addEventListener("click", function () {
    setToken(tokenInput.value.trim());
    toast("Token kaydedildi.");
    refreshStatus();
  });

  // ---------- init ----------
  refreshStatus();
  setInterval(refreshStatus, 30000);
})();
