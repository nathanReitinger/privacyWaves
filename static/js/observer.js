/* =====================================================================
   Panopti — the observer
   ---------------------------------------------------------------------
   Everything a page can notice about you without asking permission once.
   Each detector reports a bare key and value; the sentences are written
   on the server in narrate.py, so the feed you read is the log itself.

   Nothing here is exotic. Every API used below ships in every major
   browser and needs no prompt. That is the point.
   ===================================================================== */
(function () {
  "use strict";

  var QUEUE = [];
  var SENT = {};
  var lastId = 0;
  var started = Date.now();

  /* push a signal. `always` re-narrates on every send rather than once. */
  function sig(k, v, v2, always) {
    var fp = k + "|" + (always ? Math.random() : "");
    if (!always && SENT[k] !== undefined && SENT[k] === String(v)) return;
    SENT[k] = String(v);
    QUEUE.push({ k: k, v: v === undefined ? null : v, v2: v2 || null, always: !!always });
  }
  window.PanoptiSignal = sig;

  function flush() {
    if (!QUEUE.length) return;
    var batch = QUEUE.splice(0, 60);
    fetch("/api/observe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ signals: batch, since: lastId })
    }).then(function (r) { return r.json(); })
      .then(function (e) {
        if (e && e.feed && window.PanoptiFeed) window.PanoptiFeed(e.feed, e.feed_total);
        if (e && e.dossier && window.applyEnvelopeExternal) window.applyEnvelopeExternal(e);
      }).catch(function () {});
  }
  setInterval(flush, 900);

  var fmtMs = function (ms) {
    return ms < 1000 ? Math.round(ms) + " ms"
      : ms < 60000 ? (ms / 1000).toFixed(1) + " seconds"
      : Math.round(ms / 60000) + " minutes";
  };

  /* =================== arrival, time of day =================== */
  (function arrival() {
    var d = new Date(), hr = d.getHours(), day = d.getDay();
    sig("visit.hour", d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }));
    if (day >= 1 && day <= 5 && hr >= 9 && hr < 17) sig("visit.workday");
    else if (day === 0 || day === 6) sig("visit.weekend");
    if (hr >= 0 && hr < 5) sig("visit.latenight", d.toLocaleTimeString([], { hour: "numeric" }));
    if (document.referrer) {
      try { sig("visit.referrer", new URL(document.referrer).hostname); }
      catch (e) { sig("visit.referrer", "an unreadable source"); }
    } else sig("visit.direct");
  })();

  /* =================== hardware, one shot =================== */
  (function hardware() {
    var n = navigator;
    if (n.hardwareConcurrency) sig("dev.cores", n.hardwareConcurrency);
    if (n.deviceMemory) sig("dev.memory", n.deviceMemory + " GB or more");
    sig("dev.platform", n.platform || "unknown");
    sig("dev.screen", screen.width + " by " + screen.height + " pixels");
    if (window.devicePixelRatio && window.devicePixelRatio !== 1)
      sig("dev.dpr", window.devicePixelRatio + "× pixel density");
    if (n.maxTouchPoints) sig("dev.touch", n.maxTouchPoints);
    sig("dev.timezone", Intl.DateTimeFormat().resolvedOptions().timeZone || "unknown");
    sig("dev.languages", (n.languages || [n.language]).join(", "));

    try {
      var ro = Intl.DateTimeFormat().resolvedOptions();
      sig("dev.locale", ro.locale + ", " + ro.calendar + " calendar, " +
        (ro.hour12 ? "12-hour clock" : "24-hour clock"));
    } catch (e) {}

    if (n.webdriver) sig("dev.webdriver", "true");
    if (n.plugins && n.plugins.length) sig("dev.plugins", n.plugins.length);
    if (n.doNotTrack === "1" || n.globalPrivacyControl)
      sig("dev.dnt", "We are recording it as a preference and continuing.");

    if (n.userAgentData && n.userAgentData.brands) {
      sig("dev.uadata", n.userAgentData.brands.map(function (b) {
        return b.brand + " " + b.version;
      }).join(", "));
    }

    /* rendering stack */
    try {
      var c = document.createElement("canvas");
      var gl = c.getContext("webgl") || c.getContext("experimental-webgl");
      if (gl) {
        var dbg = gl.getExtension("WEBGL_debug_renderer_info");
        if (dbg) sig("dev.gpu", gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL));
      }
    } catch (e) {}

    /* audio stack fingerprint — no sound is produced */
    try {
      var AC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
      if (AC) {
        var ctx = new AC(1, 44100, 44100);
        var osc = ctx.createOscillator(); osc.type = "triangle";
        osc.frequency.value = 10000;
        var comp = ctx.createDynamicsCompressor();
        osc.connect(comp); comp.connect(ctx.destination);
        osc.start(0); ctx.startRendering();
        ctx.oncomplete = function (ev) {
          var sum = 0, data = ev.renderedBuffer.getChannelData(0);
          for (var i = 4500; i < 5000; i++) sum += Math.abs(data[i]);
          sig("dev.audio", sum.toString(16).slice(0, 12));
        };
      }
    } catch (e) {}

    /* media hardware: counts and kinds, without a permission prompt */
    if (n.mediaDevices && n.mediaDevices.enumerateDevices) {
      n.mediaDevices.enumerateDevices().then(function (list) {
        var cam = 0, mic = 0, spk = 0;
        list.forEach(function (d) {
          if (d.kind === "videoinput") cam++;
          else if (d.kind === "audioinput") mic++;
          else spk++;
        });
        var parts = [];
        if (cam) parts.push(cam + " camera" + (cam > 1 ? "s" : ""));
        if (mic) parts.push(mic + " microphone" + (mic > 1 ? "s" : ""));
        if (spk) parts.push(spk + " audio output" + (spk > 1 ? "s" : ""));
        if (parts.length) sig("dev.cameras", parts.join(", "));
      }).catch(function () {});
    }

    /* permission states, read silently */
    if (n.permissions && n.permissions.query) {
      var want = ["geolocation", "notifications", "camera", "microphone"];
      Promise.all(want.map(function (nm) {
        return n.permissions.query({ name: nm })
          .then(function (r) { return nm + ": " + r.state; })
          .catch(function () { return null; });
      })).then(function (res) {
        res = res.filter(Boolean);
        if (res.length) sig("dev.permissions", res.join(", "));
      });
    }

    if (n.storage && n.storage.estimate) {
      n.storage.estimate().then(function (est) {
        if (est.quota) sig("dev.storage", Math.round(est.quota / 1048576) + " MB");
      }).catch(function () {});
    }

    /* codec support is a few more bits of entropy */
    try {
      var v = document.createElement("video"), ok = [];
      [["H.264", 'video/mp4; codecs="avc1.42E01E"'],
       ["VP9", 'video/webm; codecs="vp9"'],
       ["AV1", 'video/mp4; codecs="av01.0.00M.08"'],
       ["HEVC", 'video/mp4; codecs="hvc1"']].forEach(function (p) {
        if (v.canPlayType(p[1])) ok.push(p[0]);
      });
      if (ok.length) sig("dev.codecs", ok.join(", "));
    } catch (e) {}

    if (performance.memory && performance.memory.jsHeapSizeLimit)
      sig("dev.heap", Math.round(performance.memory.jsHeapSizeLimit / 1048576) + " MB");

    /* accessibility preferences are health-adjacent and free to read */
    if (matchMedia("(prefers-color-scheme: dark)").matches) sig("dev.darkmode", "dark");
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) sig("dev.reducedmotion");
    if (matchMedia("(prefers-contrast: more)").matches) sig("dev.contrast", "higher contrast");

    /* battery, and its trajectory */
    if (n.getBattery) {
      n.getBattery().then(function (b) {
        var report = function () {
          var pct = Math.round(b.level * 100);
          if (pct < 25 && !b.charging) sig("dev.battery_low", pct + "%");
          else sig("dev.battery", pct + "%" + (b.charging ? ", charging" : ""));
        };
        report();
        b.addEventListener("levelchange", report);
        b.addEventListener("chargingchange", function () {
          if (b.charging) sig("dev.charging", "", "", true);
        });
      }).catch(function () {});
    }

    /* network, and whether they are paying for it */
    var conn = n.connection || n.mozConnection || n.webkitConnection;
    if (conn) {
      var net = function () {
        if (conn.effectiveType) sig("dev.network", conn.effectiveType +
          (conn.downlink ? ", about " + conn.downlink + " Mbps" : ""));
        if (conn.rtt) sig("dev.rtt", conn.rtt + " ms");
        if (conn.saveData) sig("dev.savedata");
      };
      net();
      conn.addEventListener && conn.addEventListener("change", net);
    }

    /* physical tilt, if the device has an accelerometer and offers it freely */
    if (window.DeviceOrientationEvent && !window.DeviceOrientationEvent.requestPermission) {
      var tilted = false;
      window.addEventListener("deviceorientation", function (e) {
        if (tilted || e.beta === null) return;
        tilted = true;
        sig("dev.orientation_sensor", Math.round(e.beta) + " degrees from flat");
      }, { passive: true });
    }

    /* pointer class */
    sig("dev.pointer", matchMedia("(pointer: coarse)").matches ? "finger"
      : matchMedia("(pointer: fine)").matches ? "mouse or trackpad" : "unknown device");
  })();

  /* clock skew, measured against the server's own clock */
  fetch("/api/state").then(function (r) {
    var sd = r.headers.get("date");
    if (!sd) return;
    var skew = Math.abs(Date.now() - new Date(sd).getTime());
    if (skew > 20000) sig("dev.clockskew", fmtMs(skew));
  }).catch(function () {});

  /* =================== pointer behaviour =================== */
  (function pointer() {
    var lx = null, ly = null, lastT = 0, lastDir = null, straight = 0;
    var travel = 0, idleT = null, leftAt = 0, first = true;
    var quad = { "top left": 0, "top right": 0, "bottom left": 0, "bottom right": 0 };
    var jitter = [], approaches = [];
    var marks = { 1000: "mouse.travel1k", 10000: "mouse.travel10k", 100000: "mouse.travel100k" };
    var hit = {};

    function idleReset(ms, key) {
      clearTimeout(idleT);
      idleT = setTimeout(function () { sig(key || "mouse.idle10"); }, ms || 10000);
    }

    document.addEventListener("mousemove", function (e) {
      var now = performance.now();
      if (first) { first = false; sig("mouse.first"); }
      idleReset(10000, "mouse.idle10");

      if (lx !== null) {
        var dx = e.clientX - lx, dy = e.clientY - ly;
        var dist = Math.sqrt(dx * dx + dy * dy);
        travel += dist;
        Object.keys(marks).forEach(function (m) {
          if (travel > +m && !hit[m]) { hit[m] = 1; sig(marks[m]); }
        });

        var dt = (now - lastT) / 1000;
        if (dt > 0 && dist > 1) {
          var speed = dist / dt;
          if (speed > 2200) sig("mouse.fast", Math.round(speed) + " pixels a second");
          else if (speed < 40) sig("mouse.veryslow");
          else if (speed < 120) sig("mouse.slow", Math.round(speed) + " pixels a second");
        }

        if (Math.abs(dx) > Math.abs(dy)) {
          if (dx > 2) sig("mouse.right"); else if (dx < -2) sig("mouse.left");
        } else {
          if (dy > 2) sig("mouse.down"); else if (dy < -2) sig("mouse.up");
        }

        var dir = Math.atan2(dy, dx);
        if (lastDir !== null) {
          var turn = Math.abs(dir - lastDir);
          if (turn > Math.PI * 0.75 && dist > 4) { sig("mouse.turn"); straight = 0; }
          else if (turn < 0.12) {
            straight += dist;
            if (straight > 500) sig("mouse.straight500");
            else if (straight > 100) sig("mouse.straight100");
            else if (straight > 10) sig("mouse.straight10");
          } else straight = 0;
          jitter.push(turn);
          if (jitter.length === 120) {
            var avg = jitter.reduce(function (a, b) { return a + b; }, 0) / jitter.length;
            sig(avg > 1.05 ? "mouse.tremor" : avg < 0.25 ? "mouse.steady" : "mouse.steady");
            jitter = [];
          }
        }
        lastDir = dir;
      }

      var q = (e.clientY < innerHeight / 2 ? "top " : "bottom ") +
              (e.clientX < innerWidth / 2 ? "left" : "right");
      quad[q]++;

      lx = e.clientX; ly = e.clientY; lastT = now;
    }, { passive: true });

    /* which corner they live in */
    setTimeout(function () {
      var best = Object.keys(quad).sort(function (a, b) { return quad[b] - quad[a]; })[0];
      if (quad[best] > 30) sig("mouse.quadrant", best);
    }, 45000);

    /* approach angle is a decent handedness tell */
    document.addEventListener("mouseover", function (e) {
      var t = e.target.closest && e.target.closest(".add, .btn-primary, .rbtn");
      if (!t || lx === null) return;
      var r = t.getBoundingClientRect();
      approaches.push(lx < r.left + r.width / 2 ? -1 : 1);
      if (approaches.length === 8) {
        var sum = approaches.reduce(function (a, b) { return a + b; }, 0);
        if (Math.abs(sum) >= 5)
          sig("mouse.approach", sum < 0 ? "left" : "right", sum < 0 ? "right" : "left");
        approaches = [];
      }
    });

    document.addEventListener("mouseleave", function () {
      leftAt = Date.now(); sig("mouse.left_window", "", "", true);
    });
    document.addEventListener("mouseenter", function () {
      if (leftAt) sig("mouse.returned", fmtMs(Date.now() - leftAt), "", true);
      leftAt = 0;
    });
  })();

  /* =================== clicks =================== */
  (function clicks() {
    var n = 0, firstAt = 0, times = [], lastPos = null, run = 0;
    var marks = { 1: 1, 5: 1, 10: 1, 25: 1, 50: 1, 100: 1, 250: 1 };
    var offsets = [];

    document.addEventListener("click", function (e) {
      n++;
      var now = Date.now();
      if (!firstAt) {
        firstAt = now;
        var ms = now - started;
        sig("click.first", fmtMs(ms), ms < 4000 ? "faster" : "slower");
      }
      if (marks[n]) sig("click.count", n);

      times.push(now);
      times = times.filter(function (t) { return now - t < 1000; });
      if (times.length >= 5) sig("click.rate", times.length, "", true);

      if (lastPos && Math.abs(lastPos.x - e.clientX) < 12 &&
          Math.abs(lastPos.y - e.clientY) < 12 && now - lastPos.t < 450) {
        run++;
        if (run === 1) sig("click.double");
        if (run === 2) sig("click.triple");
        if (run >= 4) sig("click.rage", "", "", true);
      } else run = 0;
      lastPos = { x: e.clientX, y: e.clientY, t: now };

      var btn = e.target.closest && e.target.closest("button, a");
      if (!btn) sig("click.outside");
      else {
        var r = btn.getBoundingClientRect();
        offsets.push(Math.hypot(e.clientX - (r.left + r.width / 2),
                                e.clientY - (r.top + r.height / 2)));
        if (offsets.length === 10) {
          var avg = offsets.reduce(function (a, b) { return a + b; }, 0) / 10;
          sig("click.precision", Math.round(avg) + " pixels");
          offsets = [];
        }
      }
    }, { passive: true });

    document.addEventListener("contextmenu", function (e) {
      var art = e.target.closest && e.target.closest(".thumb, img");
      if (art) sig("click.right_image", "", "", true);
      else sig("click.right");
    });

    document.addEventListener("dragstart", function () { sig("click.drag"); });
  })();

  /* =================== keyboard =================== */
  (function keys() {
    var first = true, back = 0, last = 0, gaps = [];
    document.addEventListener("keydown", function (e) {
      if (first) { first = false; sig("key.first"); }
      var now = Date.now();
      if (last) {
        gaps.push(now - last);
        if (gaps.length === 25) {
          gaps.sort(function (a, b) { return a - b; });
          sig("key.speed", gaps[12] + " ms");
          gaps = [];
        }
      }
      last = now;

      if (e.key === "Backspace") {
        back++;
        if (back === 1) sig("key.backspace");
        if (back === 12) sig("key.backspace_many", back);
      }
      if (e.key === "Tab") sig("key.tab");
      if (e.key === "Escape") sig("key.escape");
      if (e.key === "F12") sig("key.devtools");

      var mod = e.metaKey || e.ctrlKey;
      if (mod && e.key === "s") sig("key.save");
      if (mod && e.key === "p") sig("key.print");
      if (mod && e.key === "f") sig("key.find");
      if (mod && e.key === "a") sig("key.selectall");
      if (mod && e.key === "r") sig("key.reload");
      if (mod && e.shiftKey && (e.key === "I" || e.key === "J" || e.key === "C"))
        sig("key.devtools");
    }, { passive: true });

    document.addEventListener("paste", function () { sig("key.paste", "", "", true); });
    document.addEventListener("copy", function () { sig("key.copy", "", "", true); });
    document.addEventListener("cut", function () { sig("key.cut", "", "", true); });
    document.addEventListener("mouseup", function () {
      var t = String(window.getSelection());
      if (t.length > 12) sig("sel.text", t.length + " characters", "", true);
    }, { passive: true });
  })();

  /* =================== the window =================== */
  (function win() {
    var awayAt = 0, maxDepth = 0, lastY = 0, up = false, down = false;
    var wide = {};

    function size() {
      sig("win.size", innerWidth + " by " + innerHeight + " pixels");
      sig("win.orientation", innerWidth >= innerHeight ? "landscape" : "portrait");
      if (innerWidth > 2000 && !wide[2000]) { wide[2000] = 1; sig("win.wide", "2000 pixels"); }
      else if (innerWidth > 1000 && !wide[1000]) { wide[1000] = 1; sig("win.wide", "1000 pixels"); }
      if (innerWidth < 600) sig("win.narrow");
    }
    size();
    var rt;
    addEventListener("resize", function () {
      clearTimeout(rt);
      rt = setTimeout(function () { sig("win.resize", "", "", true); size(); }, 350);
    }, { passive: true });

    var dpr = devicePixelRatio;
    setInterval(function () {
      if (devicePixelRatio !== dpr) {
        dpr = devicePixelRatio;
        sig("win.zoom", Math.round(dpr * 100) + "%", "", true);
      }
    }, 1500);

    addEventListener("beforeprint", function () { sig("key.print", "", "", true); });
    document.addEventListener("fullscreenchange", function () {
      if (document.fullscreenElement) sig("win.fullscreen");
    });

    document.addEventListener("visibilitychange", function () {
      if (document.hidden) { awayAt = Date.now(); sig("win.blur", "", "", true); }
      else if (awayAt) {
        var gone = Date.now() - awayAt;
        if (gone > 120000) sig("win.away_long", fmtMs(gone), "", true);
        else sig("win.focus", fmtMs(gone), "", true);
        awayAt = 0;
      }
    });

    function onScroll(el) {
      var top = el === window ? scrollY : el.scrollTop;
      var h = el === window ? document.body.scrollHeight : el.scrollHeight;
      var vh = el === window ? innerHeight : el.clientHeight;
      if (top > lastY + 40) { if (!down) { down = true; sig("win.scroll_down"); } }
      else if (top < lastY - 40) { if (!up) { up = true; sig("win.scroll_up"); } }
      lastY = top;
      var pct = Math.min(100, Math.round(((top + vh) / h) * 100));
      if (pct > maxDepth + 24) {
        maxDepth = pct;
        if (pct >= 98) sig("win.scroll_bottom");
        else sig("win.scroll_depth", pct + "%");
      }
    }
    addEventListener("scroll", function () { onScroll(window); }, { passive: true });
    var sp = document.getElementById("shopPane");
    if (sp) sp.addEventListener("scroll", function () { onScroll(sp); }, { passive: true });
  })();

  /* =================== the interface itself =================== */
  (function ui() {
    document.addEventListener("focusin", function (e) {
      if (e.target.dataset && e.target.dataset.f) sig("form.focus", e.target.dataset.f);
    });
    document.addEventListener("focusout", function (e) {
      if (e.target.dataset && e.target.dataset.f && !e.target.value)
        sig("form.abandon", e.target.dataset.f, "", true);
    });
    document.addEventListener("click", function (e) {
      var t = e.target.closest && e.target.closest("[data-tab]");
      if (t && t.dataset.tab === "rights") sig("tab.rights");
      if (e.target.closest && e.target.closest("[data-right], [data-hub]")) sig("rights.used");
    });
  })();

  flush();
})();
