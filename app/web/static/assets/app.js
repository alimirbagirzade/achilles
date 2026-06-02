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
    });
  });

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
            pdfH.innerHTML = "yalnız .pdf · maks " + MAX_UPLOAD_MB + "&nbsp;MB · içerik doğrulanır";
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

    api("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, top_k: topk }),
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
    var badge = data.llm_used
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
  function loadPapers() {
    var list = document.getElementById("papersList");
    list.innerHTML = '<div class="empty"><span class="spinner"></span> yükleniyor…</div>';
    api("/papers", { method: "GET" })
      .then(function (papers) {
        if (!papers.length) {
          list.innerHTML = '<div class="empty">Henüz makale yok. Yukarıdan PDF yükle.</div>';
          return;
        }
        list.innerHTML = papers
          .map(function (p) {
            var btn = p.has_card
              ? '<button class="btn btn-done" disabled>✓ KART VAR</button>'
              : '<button class="btn card-btn" data-id="' + esc(p.paper_id) + '">BİLGİ KARTI</button>';
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
      })
      .catch(function (err) {
        list.innerHTML = '<div class="empty">Hata: ' + esc(err.message) + "</div>";
      });
  }

  function makeCard(paperId, btn) {
    btn.disabled = true;
    btn.classList.remove("btn-err");
    btn.innerHTML = '<span class="spinner"></span>ÜRETİLİYOR';
    api("/card/" + encodeURIComponent(paperId), { method: "POST" })
      .then(function () {
        toast("Bilgi kartı üretildi: " + paperId);
        btn.classList.remove("card-btn");
        btn.classList.add("btn-done");
        btn.textContent = "✓ KART HAZIR";
        btn.disabled = true;
        var row = btn.closest(".paper-row");
        if (row) row.classList.add("has-card");
      })
      .catch(function (err) {
        toast(err.message, true);
        btn.classList.add("btn-err");
        btn.textContent = "✕ HATA — TEKRAR DENE";
        btn.disabled = false;
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
      uploadFile(e.dataTransfer.files[0]);
    }
  });
  input.addEventListener("change", function () {
    if (input.files && input.files.length) uploadFile(input.files[0]);
  });

  function uploadFile(file) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      toast("Yalnız .pdf kabul edilir.", true);
      return;
    }
    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
      toast("Dosya " + MAX_UPLOAD_MB + " MB sınırını aşıyor.", true);
      return;
    }
    var fd = new FormData();
    fd.append("file", file);
    toast("Yükleniyor: " + file.name + " …");
    api("/papers/upload", { method: "POST", body: fd })
      .then(function (r) {
        toast(file.name + " → " + r.message);
        loadPapers();
        refreshStatus();
      })
      .catch(function (err) {
        toast("Yükleme hatası: " + err.message, true);
      });
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
