/* =====================================================================
   Panopti front end. The browser collects, the server decides and stores.
   Every panel on the right is rendered from what came back from Flask.
   ===================================================================== */
(function () {
"use strict";

var $ = function (s) { return document.querySelector(s); };
var $$ = function (s) { return Array.prototype.slice.call(document.querySelectorAll(s)); };
var CAT = window.CATALOG || [];
var ST = window.INITIAL_STATE || { version: 1, consent: {} };
var PRODUCTS = {};
CAT.forEach(function (c) {
  c.items.forEach(function (i) { PRODUCTS[i.id] = Object.assign({}, i, { coll: c.name }); });
});

/* pending telemetry, flushed by the beacon */
var P = { travel: 0, samples: 0, speed: 0, x: 0, y: 0, clicks: 0, rage: 0, scroll: 0,
          keys: 0, backspaces: 0, copies: 0, blurs: 0, blurMs: 0 };
var pendingViews = {}, pendingSearches = [], pendingEvents = [];
var started = Date.now(), minuteClock = 0, cart = [], search = "", dossier = {};

function usd(n) { return "$" + Number(n).toLocaleString(); }
var esc = function (s) {
  return String(s).replace(/[&<>]/g, function (m) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[m];
  });
};

var toastT;
function toast(m) {
  var t = $("#toast"); t.textContent = m; t.classList.add("on");
  clearTimeout(toastT); toastT = setTimeout(function () { t.classList.remove("on"); }, 2800);
}

function api(path, body) {
  return fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body || {})
  }).then(function (r) { return r.json(); });
}

var adRefreshT = null;
function refreshAdSoon() {
  clearTimeout(adRefreshT);
  adRefreshT = setTimeout(function () { if (window.reloadAd) window.reloadAd(); }, 400);
}

var lastAdKey = null;
function paintFooter() {
  var n = $("#footNote"), l = $("#partnersLink");
  if (!n) return;
  if (ST.version === 2) {
    n.textContent = "Every organisation that receives your data is named in section 4 " +
      "of the privacy notice, with what it gets and why.";
    if (l) l.textContent = "Who receives your data";
  } else {
    n.textContent = "Panopti Ltd, 4 Pocklington Yard, London EC1A 4XY. " +
      "We work with approximately 1,800 partners.";
    if (l) l.textContent = "Partners";
  }
}

function applyEnvelope(e) {
  if (!e) return;
  if (e.state) {
    ST = e.state;
    /* if anything that governs targeting moved, pull a fresh ad so the change
       is visible on the page rather than only in the JSON */
    var key = [ST.version, ST.restricted, ST.automated_stopped, ST.objected,
               ST.withdrawn, ST.erased, (ST.consent || {}).ads].join("|");
    if (lastAdKey !== null && key !== lastAdKey) refreshAdSoon();
    lastAdKey = key;
    document.body.dataset.version = String(ST.version);
    $("#v1").setAttribute("aria-pressed", String(ST.version === 1));
    $("#v2").setAttribute("aria-pressed", String(ST.version === 2));
  }
  if (e.cart) { cart = e.cart; updateCartBadge(); }
  if (e.rewards) paintPoints(e.rewards);
  if (e.summary && e.summary.tiers) paintPoints(e.summary);
  if (e.dossier) {
    dossier = e.dossier;
    if (e.dossier.activity_log && e.dossier.activity_log.logged !== undefined) {
      lastLogCount = e.dossier.activity_log.logged;
    }
    paintDossier(e.dossier, e.events || 0);
  }
  renderRights();
  paintFooter();
}

/* ====================== marketplace ====================== */
function matches(p, q) {
  return (p.n + " " + p.b + " " + p.coll).toLowerCase().indexOf(q) !== -1;
}
/* Half the catalogue is a plain emoji, half is generated pixel art. Both carry
   their own digest, so the mix never costs you the proof that they differ. */
function tile(p, small) {
  if (p.e) return '<span class="emoji" role="img" aria-label="' + esc(p.n) + '">' + p.e + "</span>";
  var d = small ? 56 : 192;
  return '<img src="/art/' + p.id + '.svg" alt="Generated artwork for ' + esc(p.n) +
    '" loading="lazy" width="' + d + '" height="' + d + '">';
}

function renderGrid() {
  var q = search.trim().toLowerCase(), host = $("#collections");
  var total = 0;
  var html = CAT.map(function (c) {
    var items = c.items.filter(function (i) {
      return !q || matches(Object.assign({ coll: c.name }, i), q);
    });
    total += items.length;
    if (!items.length) return "";
    return '<section class="coll"><div class="coll-head"><h3>' + esc(c.name) + "</h3>" +
      '<span class="verified">verified</span><span class="meta">' + esc(c.blurb) +
      " &middot; floor " + usd(c.floor) + "</span></div><div class=\"grid\">" +
      items.map(function (p, ix) {
        /* `card`, not `tile`: tile() is the artwork helper and a local of the
           same name shadows it, which silently empties the whole grid. */
        var card = '<article class="card" data-id="' + p.id + '">' +
          '<div class="thumb">' + tile(p) +
          '<span class="stylechip">' + esc(p.style) + "</span>" +
          '<span class="hashtag">#' + esc(p.hash) + "</span></div>" +
          "<h4>" + esc(p.n) + "</h4>" +
          '<p class="blurb">' + esc(p.b) + "</p>" +
          '<div class="row"><span class="price">' + usd(p.p) + "</span>" +
          '<button class="add" data-add="' + p.id + '">Mint</button></div>' +
          '<p class="agree-micro">Minting confirms you accept the Terms, the Notice and onward data sharing.</p>' +
          "</article>";
        /* An ad after every third token, so whatever the column count, every
           row carries one. This is roughly the density of a real marketplace,
           which is the uncomfortable part. */
        return card + ((ix + 1) % 3 === 0 ? nextAdTile() : "");
      }).join("") + nextAdTile() + "</div></section>";
  }).join("");
  $("#countline").innerHTML = q
    ? '<span class="chip">' + total + " results</span><span>for &ldquo;" + esc(search) + "&rdquo;</span>"
    : '<span class="chip">' + window.TOKEN_COUNT + " shown</span><span>of 12,842 in this drop " +
      "&middot; every artwork generated from its own SHA-256 &middot; fees included</span>";
  host.innerHTML = html || '<p class="empty">Nothing matches <b>' + esc(search) + "</b>.</p>";
}
function cartCount() { return cart.reduce(function (a, b) { return a + b.qty; }, 0); }
function cartTotal() {
  return cart.reduce(function (a, b) {
    return a + (PRODUCTS[b.token_id] ? PRODUCTS[b.token_id].p * b.qty : 0);
  }, 0);
}
function updateCartBadge() { $("#cartCount").textContent = cartCount(); }

/* ====================== cart & mint ====================== */
var checkoutMode = false, minted = false, lastOrder = null;
var checkoutDraft = {};
function openDrawer() { $("#drawerBack").classList.add("on"); $("#drawer").classList.add("on"); renderDrawer(); }
function closeDrawer() {
  $("#drawerBack").classList.remove("on"); $("#drawer").classList.remove("on");
  checkoutMode = false; minted = false;
}
function renderDrawer() {
  var body = $("#drawerBody"), foot = $("#drawerFoot"), title = $("#drawerTitle");
  if (minted) {
    title.textContent = "Order placed";
    body.innerHTML = '<div class="done"><div class="tick">&#127881;</div><h4>Thanks, that is logged</h4>' +
      "<p>Order #" + lastOrder + " written to the database. No money moved. " + (ST.version === 1
        ? "Your details have been shared with our partners to improve your experience."
        : "Your details were used for this mint only. Nothing was shared.") + "</p></div>";
    foot.innerHTML = '<button class="btn-ghost" id="keepShopping">Keep browsing</button>';
    $("#keepShopping").onclick = closeDrawer;
    return;
  }
  if (!cart.length && !checkoutMode) {
    title.textContent = "Your cart";
    body.innerHTML = '<p class="empty">Nothing queued yet.</p>';
    foot.innerHTML = ""; return;
  }
  if (!checkoutMode) {
    title.textContent = "Your cart";
    body.innerHTML = cart.map(function (c) {
      var p = PRODUCTS[c.token_id]; if (!p) return "";
      return '<div class="line"><span class="linethumb">' + tile(p, true) + "</span>" +
        '<span class="nm">' + esc(p.n) + (c.qty > 1 ? " <b>&times;" + c.qty + "</b>" : "") +
        '<br><button data-rm="' + p.id + '">Remove</button></span>' +
        '<span class="pr">' + usd(p.p * c.qty) + "</span></div>";
    }).join("");
    foot.innerHTML = '<div class="totalrow"><span>Total</span><span>' + usd(cartTotal()) + "</span></div>" +
      '<button class="btn-primary" id="toCheckout">Checkout</button>';
    $("#toCheckout").onclick = function () { checkoutMode = true; renderDrawer(); };
    $$("#drawerBody [data-rm]").forEach(function (b) {
      b.onclick = function () {
        api("/api/cart", { token_id: b.dataset.rm, op: "remove" }).then(function (e) {
          applyEnvelope(e); renderDrawer();
        });
      };
    });
    return;
  }
  title.textContent = "Checkout";
  body.innerHTML =
    '<div class="wallet' + (ST.wallet ? " on" : "") + '"><h5>' +
      (ST.wallet ? "Custodial wallet" : "A wallet will be created for you") + "</h5>" +
      "<p>No extension, no seed phrase, no connect step. We make one and hold it." +
      (ST.version === 1 ? " It is linked to every name you give us." : "") + "</p>" +
      (ST.wallet ? '<div class="addr">' + esc(ST.wallet) + "</div>" : "") +
    "</div>" +
    multifield("name", "Full name", "Jordan Alvarez", "another name") +
    multifield("email", "Email", "you@example.com", "another email") +
    multifield("phone", "Phone", "Optional", "another number") +
    multifield("addr1", "Delivery address", "Street and number", "another address") +
    '<div class="two">' + field("city", "City", "") + field("zip", "Postcode", "") + "</div>" +
    '<p class="checkout-note">Nothing is charged. This is a demonstration: the order is ' +
      "written to the database exactly as a real one would be, and that is the whole point.</p>";

  foot.innerHTML = '<div class="totalrow"><span>Total</span><span>' + usd(cartTotal()) +
    "</span></div>" +
    '<button class="btn-primary" id="placeOrder">Buy ' + cartCount() +
    " item" + (cartCount() === 1 ? "" : "s") + " &middot; " + usd(cartTotal()) + "</button>";

  wireCheckoutFields();
  $("#placeOrder").onclick = function () {
    var v = collectFields();
    if (!v.name.length || !v.addr1.length) {
      toast("A name and an address are needed to deliver it"); return;
    }
    api("/api/order", v).then(function (e) {
      if (e.error) { toast(e.error); return; }
      lastOrder = e.order_id; minted = true; applyEnvelope(e); renderDrawer();
    });
  };
}

/* Repeatable fields. People have more than one email address, change their
   name, and move house. The database keeps every value, so the form offers
   every value. */
var MULTI = ["name", "email", "phone", "addr1"];
var extra = {};

function field(id, label, ph) {
  return '<div class="field"><label for="f-' + id + '">' + esc(label) + "</label>" +
    '<input id="f-' + id + '" data-f="' + id + '" placeholder="' + esc(ph) + '"></div>';
}

function multifield(id, label, ph, addLabel) {
  var n = extra[id] || 1, rows = "";
  for (var i = 0; i < n; i++) {
    rows += '<div class="mrow"><input id="f-' + id + "-" + i + '" data-f="' + id +
      '" data-ix="' + i + '" placeholder="' + esc(i ? addLabel : ph) + '">' +
      (i ? '<button class="mdel" data-del="' + id + '" data-ix="' + i +
           '" aria-label="Remove this ' + esc(id) + '">&times;</button>' : "") +
      "</div>";
  }
  return '<div class="field multi" data-group="' + id + '">' +
    '<label for="f-' + id + '-0">' + esc(label) +
    (n > 1 ? ' <span class="mcount">' + n + " values</span>" : "") + "</label>" +
    rows + '<button class="madd" data-add-f="' + id + '">+ add ' + esc(addLabel) +
    "</button></div>";
}

function collectFields() {
  var v = { name: [], email: [], phone: [], addr1: [], city: [], zip: [] };
  $$("#drawerBody [data-f]").forEach(function (i) {
    var val = (i.value || "").trim();
    if (val && v[i.dataset.f]) v[i.dataset.f].push(val);
  });
  return v;
}

function wireCheckoutFields() {
  $$("#drawerBody [data-f]").forEach(function (inp) {
    var saved = (checkoutDraft[inp.dataset.f] || [])[inp.dataset.ix || 0];
    if (saved) inp.value = saved;
    inp.addEventListener("input", function () {
      var g = checkoutDraft[inp.dataset.f] || (checkoutDraft[inp.dataset.f] = []);
      g[inp.dataset.ix || 0] = inp.value;
      // v1 writes every keystroke straight to the server, before any button is pressed
      if (ST.version === 1) {
        api("/api/checkout/field", { field: inp.dataset.f, value: inp.value })
          .then(function (e) { if (e && e.dossier) applyEnvelope(e); });
      }
    });
  });
  $$("#drawerBody [data-add-f]").forEach(function (b) {
    b.onclick = function () {
      var id = b.dataset.addF;
      extra[id] = (extra[id] || 1) + 1;
      renderDrawer();
      var last = $("#f-" + id + "-" + (extra[id] - 1));
      if (last) last.focus();
    };
  });
  $$("#drawerBody [data-del]").forEach(function (b) {
    b.onclick = function () {
      var id = b.dataset.del, ix = +b.dataset.ix;
      (checkoutDraft[id] || []).splice(ix, 1);
      extra[id] = Math.max(1, (extra[id] || 1) - 1);
      renderDrawer();
    };
  });
}


/* The activity log lives inside the dossier now, as one collapsible section.
   Narrating every pointer movement in a separate pane was accurate and
   exhausting; milestones in context are easier to actually read. */
window.applyEnvelopeExternal = function (e) { applyEnvelope(e); };



/* ====================== keeping the log live ======================
   /api/feed is a two-field response, so this can run often and cheaply.
   A full repaint only happens when the count actually moves. */
var lastLogCount = -1, logTimer = null;

function pollRewards() {
  fetch("/api/rewards").then(function (r) { return r.json(); })
    .then(function (d) { if (d && d.points !== undefined) paintPoints(d); })
    .catch(function () {});
}

function pollLog() {
  pollRewards();
  fetch("/api/feed?since=0")
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (!d || typeof d.total !== "number") return;
      if (d.total === lastLogCount) return;
      var first = lastLogCount === -1;
      lastLogCount = d.total;
      if (first) { paintLogInto(d.feed); return; }
      fetch("/api/state").then(function (r) { return r.json(); }).then(applyEnvelope);
    })
    .catch(function () {});
}

/* Patch just the log's own <pre> between full repaints, so new lines appear
   without rebuilding the panel underneath the reader's cursor. */
function paintLogInto(rows) {
  var pre = document.querySelector('#wBody details[data-k="activity_log"] pre.json');
  if (!pre || !rows || !rows.length) return;
  var lines = rows.map(function (r) {
    var t = new Date(r.ts * 1000).toLocaleTimeString([], { hour12: false });
    return t + "  " + r.text;
  });
  var node = { entries: lines, logged: lines.length };
  pre.innerHTML = renderNode(node, 0, "/activity_log");
}

function startLogPolling() {
  clearInterval(logTimer);
  pollLog();
  logTimer = setInterval(pollLog, 2000);
  /* stop asking while the tab is hidden; resume the moment it is back */
  document.addEventListener("visibilitychange", function () {
    clearInterval(logTimer);
    if (!document.hidden) { pollLog(); logTimer = setInterval(pollLog, 2000); }
  });
}



/* ====================== the large view ====================== */
function openToken(tid) {
  fetch("/api/token/" + encodeURIComponent(tid))
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (d.error) return;
      if (d.envelope) applyEnvelope(d.envelope);
      var a = d.artist;
      var art = d.emoji
        ? '<span class="bigemoji" role="img" aria-label="' + esc(d.name) + '">' + d.emoji + "</span>"
        : '<img src="/art/' + d.id + '.svg" alt="Artwork for ' + esc(d.name) + '">';
      $("#viewerBack").classList.add("on");
      $("#viewer").innerHTML =
        '<button class="vclose" id="vClose" aria-label="Close">&times;</button>' +
        '<div class="vart">' + art + "</div>" +
        '<div class="vmeta">' +
          '<p class="vcoll">' + esc(d.collection) + " \u00b7 " + esc(d.edition) + "</p>" +
          "<h2>" + esc(d.name) + "</h2>" +
          '<p class="vblurb">' + esc(d.blurb) + "</p>" +

          '<div class="vartist">' +
            '<div class="vavatar">' + esc(a.name.charAt(0)) + "</div>" +
            "<div><strong>" + esc(a.name) + '</strong> <span class="vhandle">' +
              esc(a.handle) + "</span>" +
              "<p>" + esc(a.city) + " \u00b7 " + esc(a.medium) + " \u00b7 " +
              a.works + " works since " + a.year + "</p></div>" +
          "</div>" +
          '<p class="vbio">' + esc(a.bio) + "</p>" +

          '<div class="vtraits">' + d.traits.map(function (t) {
            return '<div class="vtrait"><span class="tn">' + esc(t.name) + "</span>" +
              '<span class="tv">' + esc(t.value) + "</span>" +
              '<span class="tr">' + esc(t.rarity) + " have this</span></div>";
          }).join("") + "</div>" +

          '<dl class="vhash">' +
            "<dt>Token digest</dt><dd>" + esc(d.hash) + "</dd>" +
            "<dt>Rendered from</dt><dd>" + esc(d.style) +
              " \u00b7 minted at " + esc(d.minted) + "</dd>" +
          "</dl>" +
          '<p class="vproof">The artwork above is drawn from that digest. No two tokens ' +
            "can share one, which is the only claim on this page that is actually true.</p>" +

          '<div class="vbuy"><span class="vprice">' + usd(d.price) + "</span>" +
            '<button class="btn-primary vadd" data-add="' + d.id + '">Add to cart</button>' +
          "</div>" +
        "</div>";
      $("#vClose").onclick = closeToken;
      $("#viewerBack").onclick = function (ev) {
        if (ev.target === $("#viewerBack")) closeToken();
      };
      $("#viewer").querySelector(".vadd").onclick = function () {
        api("/api/cart", { token_id: d.id, op: "add" }).then(function (e) {
          applyEnvelope(e); closeToken(); toast(d.name + " added");
        });
      };
    }).catch(function () {});
}
function closeToken() { $("#viewerBack").classList.remove("on"); }

/* ====================== in-grid advertising ======================
   Native placements, sized and shaped exactly like a token so the eye does not
   separate them from the catalogue. That camouflage is the format, not an
   accident of my CSS, and the label is the only thing distinguishing them. */
var SLATE = [], slateIx = 0;

var URGENCY = ["Ends tonight", "Only 3 left", "Selling fast", "Back in stock",
               "Today only", "Limited drop", "Almost gone", "New"];

function nextAdTile() {
  if (!SLATE.length) return "";
  var ad = SLATE[slateIx % SLATE.length].ad;
  var urg = URGENCY[slateIx % URGENCY.length];
  slateIx++;
  return '<article class="card adcard tone-' + (ad.tone || "retail") + '" data-adid="' +
      ad.id + '">' +
    '<span class="adtag">Ad</span>' +
    '<span class="adurgent">' + esc(urg) + "</span>" +
    '<div class="thumb adthumb"><span class="emoji">' + ad.art + "</span></div>" +
    '<span class="adbrand">' + esc(ad.advertiser) + "</span>" +
    "<h4>" + esc(ad.headline) + "</h4>" +
    '<p class="blurb">' + esc(ad.body) + "</p>" +
    '<div class="row"><span class="price adprice">+25 pts</span>' +
    '<button class="add adgo" data-adgo="' + ad.id + '">' + esc(ad.cta) + "</button></div>" +
    '<p class="agree-micro adwhytiny">Pays us $' + (ad.cpc || 0).toFixed(2) +
      " the moment you tap</p>" +
    "</article>";
}

function convert(adId, label) {
  fetch("/api/ad/click", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: adId })
  }).then(function (r) { return r.json(); }).then(function (e) {
    applyEnvelope(e);
    if (e.summary) paintPoints(e.summary);
    toast(e.revenue
      ? "Conversion recorded. You earned " + e.points_awarded +
        " points. " + (label || e.advertiser) + " paid us $" + e.revenue.toFixed(2) + "."
      : "No conversion value. You are not being targeted, so nobody paid.");
  });
}

/* the points meter: worthless currency, prominently displayed */
function paintPoints(sum) {
  var host = $("#ptsChip");
  if (!host || !sum) return;
  lastRewards = sum;
  var pts = sum.points || 0, goal = sum.goal || 75;
  var ready = (sum.tiers || []).filter(function (t) { return t.unlocked && !t.redeemed; });
  host.className = "ptschip" + (ready.length ? " ready" : "");
  host.innerHTML =
    '<span class="ptsn">' + pts + '</span><span class="ptsl">pts</span>' +
    '<span class="ptsbar"><i style="width:' +
      Math.min(100, (pts / goal) * 100).toFixed(1) + '%"></i></span>' +
    '<span class="ptsgoal">' +
      (ready.length ? ready[ready.length - 1].tier + " unlocked \u2014 tap to claim"
                    : (sum.to_go || 0) + " to " + (sum.next_tier || "the next tier")) +
    "</span>";
  host.title = "You have earned " + pts + " points, worth $0.00.";
  host.onclick = openRewards;
}

var lastRewards = null;

function openRewards() {
  fetch("/api/rewards").then(function (r) { return r.json(); }).then(function (d) {
    lastRewards = d;
    var rates = Object.keys(d.rates || {}).map(function (k) {
      return '<li><span>' + esc(k) + "</span><b>+" + d.rates[k] + "</b></li>";
    }).join("");
    sheet("Panopti Rewards", "earn points for everything you do",
      '<p>You have <b>' + d.points + " points</b>. The more you browse, search, open "
        + "and tap, the faster they build.</p>" +
      '<ul class="ratelist">' + rates + "</ul>" +
      '<div class="tierlist">' + (d.tiers || []).map(function (t) {
        return '<div class="tierrow' + (t.unlocked ? " on" : "") + '">' +
          "<div><b>" + esc(t.tier) + "</b> \u00b7 " + esc(t.perk) +
          '<span class="tierat">' + t.at + " pts</span></div>" +
          (t.redeemed
            ? '<span class="tierdone">claimed</span>'
            : t.unlocked
              ? '<button class="sbtn pri" data-claim="' + esc(t.tier) + '">Claim</button>'
              : '<span class="tierlock">' + (t.at - d.points) + " to go</span>") +
          "</div>";
      }).join("") + "</div>" +
      '<p class="rewardnote">Points are not money, cannot be transferred, and expire with ' +
        "the session. Every one of them was issued by us, at no cost to us, in exchange " +
        "for an interaction we sold. The panel on the right shows both sides of that trade.</p>",
      '<button class="sbtn" id="sClose">Close</button>');
    $("#sClose").onclick = closeSheet;
    $$("#sheet [data-claim]").forEach(function (b) {
      b.onclick = function () {
        fetch("/api/rewards/redeem", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tier: b.dataset.claim })
        }).then(function (r) { return r.json(); }).then(function (e) {
          if (e.error) { toast(e.error); return; }
          applyEnvelope(e);
          if (e.rewards) paintPoints(e.rewards);
          closeSheet();
          toast(b.dataset.claim + " claimed: " + e.perk + ". It cost Panopti nothing.");
        });
      };
    });
  });
}

/* ====================== the ad ====================== */
var currentAd = null;

function loadAd() {
  fetch("/api/ad").then(function (r) { return r.json(); }).then(function (d) {
    currentAd = d;
    SLATE = d.slate || []; slateIx = 0;
    paintPoints(d.summary);
    if (typeof renderGrid === "function") renderGrid();
    var host = $("#adSlot");
    if (!host || !d.ad) return;
    host.className = "adslot tone-" + (d.ad.tone || "house") + (d.targeted ? " targeted" : "");
    host.innerHTML =
      '<span class="adlabel">' + (d.targeted ? "Sponsored" : "Sponsored \u00b7 untargeted") + "</span>" +
      '<div class="adart">' + d.ad.art + "</div>" +
      '<div class="adbody"><h4>' + esc(d.ad.headline) + "</h4>" +
        "<p>" + esc(d.ad.body) + "</p>" +
        '<span class="adwho">' + esc(d.ad.advertiser) + "</span></div>" +
      '<button class="adcta" id="adCta">' + esc(d.ad.cta) + "</button>" +
      '<p class="admoney">' +
        "<b>Impression served.</b> This one paid Panopti $" +
        ((d.ad.cpm || 0) / 1000).toFixed(4) + " at a $" + (d.ad.cpm || 0).toFixed(2) +
        " CPM. A conversion pays $" + (d.ad.cpc || 0).toFixed(2) + " and earns you 25 points." +
      "</p>" +
      '<p class="adwhy">' + esc(d.ad.why) + "</p>";
    $("#adCta").onclick = function () {
      fetch("/api/ad/click", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: d.ad.id })
      }).then(function (r) { return r.json(); }).then(function (e) {
        applyEnvelope(e);
        toast(d.targeted
          ? "That click just earned Panopti $" + (e.revenue || 0).toFixed(2)
          : "Nothing was earned. You are not being targeted.");
      });
    };
  }).catch(function () {});
}
window.reloadAd = loadAd;

/* ====================== accessibility and layout controls ====================== */
var FS_STEPS = [0.85, 0.925, 1, 1.12, 1.28, 1.45];
var fsIx = 2;

function applyFontScale(save) {
  document.documentElement.style.setProperty("--fs-user", FS_STEPS[fsIx]);
  var d = $("#fsDown"), u = $("#fsUp"), r = $("#fsReset");
  if (d) d.disabled = fsIx === 0;
  if (u) u.disabled = fsIx === FS_STEPS.length - 1;
  if (r) r.setAttribute("aria-pressed", String(fsIx === 2));
  if (save) {
    try { localStorage.setItem("panopti.fs", String(fsIx)); } catch (e) {}
    if (window.PanoptiSignal) {
      window.PanoptiSignal(fsIx > 2 ? "a11y.larger" : "a11y.smaller",
                           Math.round(FS_STEPS[fsIx] * 100) + "%", "", true);
    }
  }
}

function initA11y() {
  try {
    var st = localStorage.getItem("panopti.fs");
    if (st !== null && FS_STEPS[+st]) fsIx = +st;
  } catch (e) {}
  applyFontScale(false);
  $("#fsDown").onclick = function () { fsIx = Math.max(0, fsIx - 1); applyFontScale(true); };
  $("#fsUp").onclick = function () {
    fsIx = Math.min(FS_STEPS.length - 1, fsIx + 1); applyFontScale(true);
  };
  $("#fsReset").onclick = function () { fsIx = 2; applyFontScale(true); };
}

function setWatchVisible(on, save) {
  document.body.dataset.watch = on ? "on" : "off";
  var b = $("#paneToggle"), l = $("#paneToggleLabel");
  if (b) b.setAttribute("aria-pressed", String(on));
  if (l) l.textContent = on ? "Hide panel" : "Show panel";
  if (save) {
    try {
      localStorage.setItem("panopti.watch", on ? "on" : "off");
      if (on) localStorage.setItem("panopti.watchPinned", "1");
    } catch (e) {}
    if (window.PanoptiSignal) window.PanoptiSignal(on ? "pane.shown" : "pane.hidden", "", "", true);
  }
}

function initPaneControls() {
  /* The panel should be seen once, so nobody can say it was hidden, and then
     get out of the way. If the reader ever opens it deliberately it is pinned
     and stays open for good. */
  var stored = null, pinned = false;
  try {
    stored = localStorage.getItem("panopti.watch");
    pinned = localStorage.getItem("panopti.watchPinned") === "1";
  } catch (e) {}

  setWatchVisible(stored !== "off", false);

  if (!pinned && stored !== "off") {
    setTimeout(function () {
      if (document.body.dataset.watch === "off") return;
      var p = false;
      try { p = localStorage.getItem("panopti.watchPinned") === "1"; } catch (e) {}
      if (p) return;
      setWatchVisible(false, false);
      var sp = $("#showPanel");
      if (sp) {
        sp.classList.add("peek");
        setTimeout(function () { sp.classList.remove("peek"); }, 6000);
      }
      toast("The data panel is still running. Tap \u201cShow data panel\u201d to watch it.");
    }, 7000);
  }
  $("#paneToggle").onclick = function () {
    setWatchVisible(document.body.dataset.watch === "off", true);
  };
  $("#showPanel").onclick = function () { setWatchVisible(true, true); };
  var ck = $("#cookieBtn");
  if (ck) ck.onclick = openCookiePrefs;

  /* --- drag to resize --- */
  var rz = $("#resizer"), split = document.querySelector(".split");
  if (!rz || !split) return;

  try {
    var w = localStorage.getItem("panopti.watchw");
    if (w) document.documentElement.style.setProperty("--watch-w", w);
  } catch (e) {}

  function setWidth(px, save) {
    var total = split.getBoundingClientRect().width;
    var pct = Math.min(78, Math.max(18, (px / total) * 100));
    var v = pct.toFixed(1) + "%";
    document.documentElement.style.setProperty("--watch-w", v);
    if (save) { try { localStorage.setItem("panopti.watchw", v); } catch (e) {} }
  }
  function move(ev) {
    var x = ev.touches ? ev.touches[0].clientX : ev.clientX;
    setWidth(split.getBoundingClientRect().right - x, false);
  }
  function stop() {
    document.body.classList.remove("resizing");
    rz.classList.remove("dragging");
    window.removeEventListener("mousemove", move);
    window.removeEventListener("touchmove", move);
    window.removeEventListener("mouseup", stop);
    window.removeEventListener("touchend", stop);
    var cur = getComputedStyle(document.documentElement).getPropertyValue("--watch-w").trim();
    try { localStorage.setItem("panopti.watchw", cur); } catch (e) {}
  }
  function start(ev) {
    ev.preventDefault();
    document.body.classList.add("resizing");
    rz.classList.add("dragging");
    window.addEventListener("mousemove", move);
    window.addEventListener("touchmove", move, { passive: false });
    window.addEventListener("mouseup", stop);
    window.addEventListener("touchend", stop);
  }
  rz.addEventListener("mousedown", start);
  rz.addEventListener("touchstart", start, { passive: false });

  /* keyboard: the handle is a real separator, so arrows must work */
  rz.addEventListener("keydown", function (e) {
    var w = $("#watchPane").getBoundingClientRect().width;
    if (e.key === "ArrowLeft") { setWidth(w + 40, true); e.preventDefault(); }
    else if (e.key === "ArrowRight") { setWidth(w - 40, true); e.preventDefault(); }
    else if (e.key === "Home") {
      document.documentElement.style.setProperty("--watch-w", "40%");
      try { localStorage.setItem("panopti.watchw", "40%"); } catch (er) {}
      e.preventDefault();
    }
  });
}

/* ====================== dossier rendering ====================== */
var FLAG = /special_category|onward_sale|sold_to|IGNORED|never_asked|keystroke|health|pregnan|bereave|mental|political|religion|financial_stress|cross_site|canvas_fingerprint|persistent_id|ip_address|connected_wallet|identity_linked|tier/i;
var prevFlat = {}, firstRender = true;
function flatten(o, p, acc) {
  acc = acc || {}; p = p || "";
  if (o && typeof o === "object") {
    Object.keys(o).forEach(function (k) { flatten(o[k], p + "/" + k, acc); });
  } else acc[p] = o;
  return acc;
}
function renderVal(v, key, path) {
  var fresh = !firstRender && prevFlat[path] !== v ? " fresh" : "";
  if (v === null) return '<span class="nu' + fresh + '">null</span>';
  if (typeof v === "boolean") return '<span class="bo' + fresh + '">' + v + "</span>";
  if (typeof v === "number") return '<span class="n' + fresh + '">' + v + "</span>";
  var cls = /USER SELECTED/.test(v) ? " pausev" : (FLAG.test(key) || FLAG.test(String(v)) ? " flagv" : "");
  return '<span class="s' + fresh + cls + '">"' + esc(v) + '"</span>';
}
function renderNode(o, depth, path) {
  var pad = new Array(depth + 2).join("  "), padEnd = new Array(depth + 1).join("  ");
  if (Array.isArray(o)) {
    if (!o.length) return '<span class="p">[]</span>';
    return '<span class="p">[</span>\n' + o.map(function (x, i) {
      return pad + (x && typeof x === "object" ? renderNode(x, depth + 1, path + "/" + i)
                                               : renderVal(x, "", path + "/" + i));
    }).join('<span class="p">,</span>\n') + "\n" + padEnd + '<span class="p">]</span>';
  }
  var keys = Object.keys(o);
  if (!keys.length) return '<span class="p">{}</span>';
  return '<span class="p">{</span>\n' + keys.map(function (k) {
    var np = path + "/" + k, val = o[k];
    if (k.indexOf("//") === 0) return pad + '<span class="cmt">// ' + esc(val) + "</span>";
    return pad + '<span class="k">"' + esc(k) + '"</span><span class="p">: </span>' +
      (val && typeof val === "object" ? renderNode(val, depth + 1, np) : renderVal(val, k, np));
  }).join('<span class="p">,</span>\n') + "\n" + padEnd + '<span class="p">}</span>';
}
var META = {
  identity: ["Who you are", "sensitive", "b-sens"],
  wallet_and_chain: ["Your wallet, and what it links to", "sensitive", "b-sens"],
  device_and_network: ["Your device and network", "observed", "b-obs"],
  live_tracking: ["Your cursor, right now", "live", "b-obs"],
  behaviour_this_session: ["What you did, second by second", "observed", "b-obs"],
  inferences_and_profiling: ["What we decided about you", "inferred", "b-inf"],
  who_has_bought_this: ["Who has bought this already", "sensitive", "b-sens"],
  how_we_justify_this: ["How we justify it", "claimed", "b-obs"],
  consent_record: ["What you actually agreed to", "record", "b-ok"],
  processing_status: ["Processing status", "record", "b-ok"],
  retention: ["How long we keep it", "record", "b-obs"],
  what_your_browser_volunteered: ["Everything your browser volunteered", "observed", "b-obs"],
  activity_log: ["Activity log", "live", "b-obs"],
  what_you_earned_us: ["What you earned us", "sensitive", "b-sens"],
  database: ["Rows in the database", "live", "b-ok"],
  erasure: ["Erasure receipt", "record", "b-ok"]
};
function paintDossier(data, events) {
  var flat = flatten(data), body = $("#wBody"), open = {};
  $$("#wBody details").forEach(function (d) { open[d.dataset.k] = d.open; });
  var html = "";
  Object.keys(data).forEach(function (k) {
    if (k.indexOf("//") === 0) { html += '<div class="stamp">' + esc(data[k]) + "</div>"; return; }
    var m = META[k] || [k.replace(/_/g, " "), "data", "b-obs"];
    var isOpen = open[k] !== undefined ? open[k]
      : (k === "activity_log" || k === "identity" || k === "live_tracking" ||
         k === "inferences_and_profiling" || k === "what_you_earned_us" || k === "erasure");
    var val = typeof data[k] === "object" ? renderNode(data[k], 0, "/" + k)
                                          : renderVal(data[k], k, "/" + k);
    html += '<details class="sect" data-k="' + k + '"' + (isOpen ? " open" : "") + ">" +
      '<summary><span class="car">&#9654;</span><span class="n">' + esc(m[0]) + "</span>" +
      '<span class="badge ' + m[2] + '">' + m[1] + "</span></summary>" +
      '<pre class="json">' + val + "</pre></details>";
  });
  if (ST.version === 1) {
    html += '<div class="w-note"><b>Every field above was written to the database whether or ' +
      "not you clicked anything.</b> The banner changed nothing except what we can claim later.</div>";
  } else if (!ST.consent.decided) {
    html += '<div class="w-note"><b>This is what data minimisation looks like.</b> Only what is ' +
      "needed to draw the marketplace and remember your cart.</div>";
  }
  body.innerHTML = html;
  prevFlat = flat; firstRender = false;

  $("#stFields").textContent = Object.keys(flat).filter(function (p) {
    return p.indexOf("//") === -1;
  }).length;
  $("#stEvents").textContent = events;
  var sold = data.who_has_bought_this && data.who_has_bought_this.sold_to;
  $("#stParty").textContent = Array.isArray(sold) ? sold.length : 0;

  var live = $("#wLive");
  if (ST.erased) { live.innerHTML = "ERASED"; live.style.color = "var(--w-ok)"; }
  else if (ST.restricted) { live.innerHTML = "PAUSED"; live.style.color = "var(--w-warn)"; }
  else if (ST.automated_stopped) { live.innerHTML = "NO PROFILING"; live.style.color = "var(--w-warn)"; }
  else if (ST.version === 2 && !ST.consent.decided) {
    live.innerHTML = '<span class="dot" style="background:var(--w-ok)"></span>MINIMAL';
    live.style.color = "var(--w-ok)";
  } else if (ST.version === 2 && !ST.consent.profiling) {
    live.innerHTML = '<span class="dot" style="background:var(--w-ok)"></span>CONSENTED';
    live.style.color = "var(--w-ok)";
  } else { live.innerHTML = '<span class="dot"></span>COLLECTING'; live.style.color = "var(--w-flag)"; }

  $("#wTitle").textContent = ST.version === 1
    ? "What we know (and are happy to sell)" : "What we know (and what you allowed)";
  $("#wSys").textContent = ST.version === 1 ? "PAN-DMP v4.2" : "PAN-PRIV v1.0";
  $("#wSub").textContent = ST.version === 1
    ? "Assembled from this browser and stored on the server. Nothing here was typed into a form on purpose."
    : "Only what you permitted, plus what the marketplace cannot function without.";

  if (data.database) {
    var n = 0;
    Object.keys(data.database).forEach(function (k) {
      if (k.indexOf("//") !== 0) n += data.database[k];
    });
    $("#dbChip").innerHTML = "db: <b>" + n + "</b> rows";
    renderDbGrid(data.database);
  }
}
function renderDbGrid(counts) {
  var host = $("#dbGrid"); if (!host) return;
  host.innerHTML = Object.keys(counts).filter(function (k) { return k.indexOf("//") !== 0; })
    .map(function (k) {
      var kept = (k === "orders" || k === "suppression");
      return '<div class="dbcell' + (counts[k] ? "" : " zero") + (kept ? " kept" : "") + '">' +
        '<span class="n">' + counts[k] + '</span><span class="t">' + esc(k) + "</span></div>";
    }).join("");
}

/* ====================== v1 consent theatre ====================== */
var LEGAL = [
 ["1. Acceptance", "By loading, rendering, caching or otherwise causing the transmission of this Service you enter a binding agreement with Panopti Ltd, its successors, affiliates, processors and any entity acquiring substantially all of its assets. If you do not agree you must cease use immediately, though data collected before cessation is retained under clause 14."],
 ["2. Definitions", "\u201cYour Data\u201d means data relating to you. \u201cOur Data\u201d means any conclusion, score, probability, segment, cluster, inference or prediction we generate from Your Data, and is our intellectual property, not yours, for the purposes of clauses 9 and 14."],
 ["3. Agreement", "Your agreement is taken as given by continued use, by scrolling, by dismissing any notice, by inaction following notice, or by any interaction with any element of this Service, including closing this notice by any means, including the \u201c\u00d7\u201d control."],
 ["4. Collection", "We collect identifiers, device characteristics, network characteristics, behavioural telemetry, interaction timing, input cadence, cursor kinematics, wallet addresses and address clusters, and any content entered into any field whether or not that field is subsequently submitted."],
 ["5. Our interests", "Where your agreement is withheld, refused, withdrawn or found ineffective, we will where possible continue processing on the basis of our own commercial interests, which we have assessed internally and found to outweigh yours. That assessment is confidential."],
 ["6. Partners", "We disclose Your Data and Our Data to our partners, presently numbering 1,847, each applying its own notice which you are taken to have read. A current list is available on request."],
 ["7. Sensitive inferences", "Where Our Data concerns your health, sleep, mental state, family circumstances, finances, beliefs or opinions, you agree to that processing by continuing to use the Service. Such data is inferred by us and is not treated as having been provided by you."],
 ["8. Automated pricing", "Floor prices, fee estimates, offers, instalment options and support routing may be set by automated means including profiling. Outcomes may differ between users viewing identical tokens."],
 ["9. Information requests", "Requests concerning Your Data must be made in writing by post with two forms of certified identification and, where the request concerns Our Data, a reasoned explanation of why disclosure would not prejudice our commercial interests."],
 ["10. Retention", "We retain Your Data for twenty-six months. Our Data, aggregated data, pseudonymised data, backups and copies held by partners fall outside that period and are retained indefinitely."],
 ["11. Transfer", "Data is transferred to jurisdictions which may not protect it to the same standard. You agree to that transfer and waive, so far as permitted, any claim arising from it."],
 ["12. Changes", "We may vary these terms at any time without notice. The version in force is the version displayed at the time of your most recent interaction, which may differ from the version you read."],
 ["13. Waiver", "You waive any right to participate in a class, collective or representative action, and agree to individual binding arbitration in a forum of our choosing."],
 ["14. Deletion", "On a verified deletion request we will delete Your Data from our primary production database. Our Data, analytical copies, partner copies, backups, wallet clusters and training corpora are technically infeasible to isolate and are excluded from this undertaking."],
 ["15. Severability", "If any clause is unenforceable the remainder survives, and that clause is read down to the maximum extent permitted rather than struck."]
];
var BUYERS = ["Adzumi DSP", "NorthBeam Audiences", "Clearfield Identity Graph",
  "Pelham & Roe Analytics", "Marchetti Exchange", "Veridia Risk Signals",
  "OpenBid Consortium (1,284 vendors)", "Hollowtree Data Co-op"];
var nagTimer = null, nagCount = 0;

function wallV1() {
  var inner = $("#wallInner"); inner.className = "wall-inner";
  inner.innerHTML =
    '<button class="wall-x" id="wallX" aria-label="Close" title="Closing this accepts all">&#10005;</button>' +
    "<h3>We value your privacy</h3>" +
    '<div class="body"><p>We and our <b>1,847 carefully selected partners</b> store and access ' +
    "information on your device, such as cookies and unique identifiers, and process data such as " +
    "browsing behaviour, approximate and precise location, wallet activity and inferred " +
    "characteristics, to deliver personalised advertising and content, measure performance, derive " +
    "audience insight, and develop and improve products. Some partners ask your agreement. Others " +
    "rely on their own interests, which need no agreement and which you may object to separately, " +
    "per partner.</p></div>" +
    '<div class="legalbox" id="legalbox">' + LEGAL.map(function (l) {
      return "<h5>" + l[0] + "</h5><p>" + l[1] + "</p>"; }).join("") +
    '<p style="opacity:.6">Sections 16 through 47 continue and are available on request.</p></div>' +
    '<div class="legal-meta"><span id="scrollState">Scroll to the end of the terms to continue</span>' +
    "<span>15 of 47 sections shown</span></div>" +
    '<label class="chk"><input type="checkbox" id="agreeChk" disabled><span>I have read and ' +
    "understood the Terms, the Privacy Notice, the Cookie Notice, the Partner List and the " +
    "Interests Assessment, and I am over 16.</span></label>" +
    '<div class="wall-actions"><button class="big-accept" id="acceptAll">Accept all</button>' +
    '<button class="tiny-link" id="managePrefs">Manage options</button></div>' +
    '<p class="vendorline">Working with <button id="showVendors">1,847 partners</button>. ' +
    "Agreement is not required for partners relying on their own interests.</p>" +
    '<div class="vendorlist" id="vendorlist"></div>';
  $("#wall").classList.add("on");
  var box = $("#legalbox"), chk = $("#agreeChk"), st = $("#scrollState");
  box.addEventListener("scroll", function () {
    if (box.scrollTop + box.clientHeight >= box.scrollHeight - 14) {
      chk.disabled = false; st.textContent = "You may now tick the box";
    }
  });
  $("#acceptAll").onclick = function () {
    if (chk.disabled || !chk.checked) {
      toast("Please read and accept the terms first"); box.scrollTop = box.scrollHeight; return;
    }
    acceptAll();
  };
  $("#wallX").onclick = function () { acceptAll(); toast("Closing the notice is treated as acceptance"); };
  $("#managePrefs").onclick = openPrefs;
  $("#showVendors").onclick = function () {
    var vl = $("#vendorlist"); vl.classList.toggle("on");
    if (!vl.innerHTML) {
      var out = [];
      for (var i = 0; i < 70; i++) {
        out.push((i + 1) + ". " + BUYERS[i % BUYERS.length] + " \u2014 " +
          (i % 3 === 0 ? "own interests" : "agreement") + " \u2014 " +
          (i % 4 === 0 ? "842 day storage" : "indefinite"));
      }
      vl.innerHTML = out.join("<br>") + "<br>\u2026 and 1,777 more.";
    }
  };
}
function acceptAll() {
  api("/api/consent", { analytics: true, ads: true, profiling: true, share: true })
    .then(function (e) {
      $("#wall").classList.remove("on"); $("#modalBack").classList.remove("on");
      applyEnvelope(e); scheduleNag();
    });
}
var PURPOSES = [
  ["Store and access information on your device", "Cookies, local storage and device identifiers."],
  ["Use limited data to select advertising", "Ads based on this page and basic signals."],
  ["Create profiles for personalised advertising", "Build a profile from your activity across sites."],
  ["Use profiles to select personalised advertising", "Show ads chosen by that profile."],
  ["Create profiles to personalise content", "Beyond advertising: layout, floor price and ordering."],
  ["Measure advertising performance", "Attribution across devices and over time."],
  ["Understand audiences through statistics", "Combine your data with other data sets."],
  ["Develop and improve services", "Including training of predictive models."],
  ["Use precise geolocation data", "Within 500 metres, continuously, while the tab is open."],
  ["Actively scan device characteristics", "Fingerprinting, which works when cookies do not."],
  ["Link different devices to one person", "Household and workplace graphing."],
  ["Cluster wallet addresses to one person", "Join every address you have ever used."],
  ["Infer sensitive characteristics", "Health, sleep, finances, beliefs and circumstances."],
  ["Share data with partners", "1,847 partners, each with onward rights."]
];
var prefsTab = "consent";
function openPrefs() { $("#modalBack").classList.add("on"); renderPrefs(); }
function renderPrefs() {
  var rows;
  if (prefsTab === "consent") {
    rows = PURPOSES.map(function (p, i) {
      return '<div class="tog"><div class="txt"><strong>' + esc(p[0]) + "</strong><span>" +
        esc(p[1]) + '</span></div><label class="sw"><input type="checkbox" checked><i></i></label></div>';
    }).join("");
  } else if (prefsTab === "li") {
    rows = '<div class="li-note">These purposes rely on <b>our own interests</b>. They are on by ' +
      "default and do not need your agreement. You may object to each one individually, per partner.</div>" +
      PURPOSES.slice(0, 9).map(function (p) {
        return '<div class="tog"><div class="txt"><strong>' + esc(p[0]) +
          "</strong><span>Objection must be exercised per partner.</span></div>" +
          '<label class="sw"><input type="checkbox" checked><i></i></label></div>';
      }).join("");
  } else {
    rows = '<div class="li-note">Strictly necessary purposes cannot be switched off.</div>' +
      ["Security and fraud prevention", "Cart persistence", "Load balancing", "Session integrity",
       "Preference record keeping"].map(function (n) {
        return '<div class="tog"><div class="txt"><strong>' + esc(n) +
          "</strong><span>Always active.</span></div>" +
          '<label class="sw locked"><input type="checkbox" checked disabled><i></i></label></div>';
      }).join("");
  }
  $("#modal").innerHTML = '<div class="modal-head"><h3>Manage your preferences</h3>' +
    "<p>Your choices apply to this browser only, and will be requested again in 30 days, or sooner " +
    'if you clear your cookies.</p><div class="tabs" role="tablist">' +
    '<button role="tab" aria-selected="' + (prefsTab === "consent") + '" data-tab="consent">Agreement (14)</button>' +
    '<button role="tab" aria-selected="' + (prefsTab === "li") + '" data-tab="li">Our interests (9)</button>' +
    '<button role="tab" aria-selected="' + (prefsTab === "ess") + '" data-tab="ess">Strictly necessary (5)</button>' +
    '</div></div><div class="modal-body">' + rows + "</div>" +
    '<div class="modal-foot"><button class="btn-primary" style="flex:1;min-width:190px" id="pAccept">Accept all</button>' +
    '<button class="tiny-link" id="pSave">Save my choices</button>' +
    '<button class="tiny-link" id="pBack">Back</button></div>';
  $$("#modal [data-tab]").forEach(function (b) {
    b.onclick = function () { prefsTab = b.dataset.tab; renderPrefs(); };
  });
  $("#pAccept").onclick = acceptAll;
  $("#pBack").onclick = function () { $("#modalBack").classList.remove("on"); };
  $("#pSave").onclick = confirmReject;
}
function confirmReject() {
  $("#modal").innerHTML = '<div class="modal-head"><h3>Are you sure?</h3><p>Limiting processing may ' +
    "degrade your experience. You may see advertising that is less relevant, and some features may " +
    'not work as intended.</p></div><div class="modal-body"><div class="li-note">Purposes relying on ' +
    "our own interests are unaffected by this choice and will continue. To object to those, go back " +
    "and switch off each of the nine purposes individually, then object per partner.</div></div>" +
    '<div class="modal-foot"><button class="btn-primary" style="flex:1;min-width:190px" id="goBack">' +
    'Go back and keep everything on</button><button class="tiny-link" id="reallySave">' +
    "Save limited choices anyway</button></div>";
  $("#goBack").onclick = function () { prefsTab = "consent"; renderPrefs(); };
  $("#reallySave").onclick = function () {
    api("/api/consent", { analytics: true, ads: false, profiling: true, share: true })
      .then(function (e) {
        $("#modalBack").classList.remove("on"); $("#wall").classList.remove("on");
        applyEnvelope(e);
        toast("Preferences saved. Essential processing continues under our own interests.");
        scheduleNag();
      });
  };
}
function scheduleNag() { clearTimeout(nagTimer); nagTimer = setTimeout(maybeNag, 45000); }
function maybeNag() {
  if (ST.version !== 1 || nagCount >= 3) return;
  nagCount++;
  var n = $("#nag");
  n.innerHTML = "<strong>Your preferences are expiring</strong>We noticed you have not confirmed " +
    "your choices recently. Confirm now to keep the marketplace working as expected." +
    '<div class="r"><button class="y" id="nagYes">Confirm all</button>' +
    '<button class="tiny-link" id="nagNo">Later</button></div>';
  n.classList.add("on");
  $("#nagYes").onclick = function () { acceptAll(); n.classList.remove("on"); };
  $("#nagNo").onclick = function () { n.classList.remove("on"); scheduleNag(); };
}

/* ====================== v2 honest consent ====================== */
function tog(id, title, sub) {
  return '<div class="tog"><div class="txt"><strong>' + esc(title) + "</strong><span>" +
    esc(sub) + '</span></div><label class="sw"><input type="checkbox" id="t-' + id +
    '"><i></i></label></div>';
}
/* The nine purposes v2 counts as "strictly necessary".
   This is the realistic part. Even a compliant site decides for itself what
   is necessary, and the category is always read generously: fraud, security
   and session are genuinely required; aggregate measurement, "service
   improvement" and core personalisation are judgement calls that happen to
   favour the site. None of them can be switched off, and none of them ask. */
var NECESSARY = [
  ["Security and fraud prevention", "Device and network characteristics, retained 26 months."],
  ["Session and cart", "So your cart survives a refresh."],
  ["Load balancing and delivery", "Your IP and rough location, at every request."],
  ["Consent record keeping", "A record of this dialogue, kept six years as evidence."],
  ["Aggregate audience measurement", "Counted as necessary because we operate the service."],
  ["Service improvement and debugging", "Interaction telemetry, read as operational data."],
  ["Core personalisation", "Ordering and layout, which we consider part of the product."],
  ["Abuse and rate limiting", "Request patterns and a durable device identifier."],
  ["Legal and tax records", "Six years, and an erasure request does not reach them."],
];

function necessaryBlock() {
  return '<details class="neccy"><summary>' +
    '<span class="neclabel">Strictly necessary</span>' +
    '<span class="necalways">Always on</span>' +
    '<span class="neccount">' + NECESSARY.length + " purposes \u00b7 view</span></summary>" +
    NECESSARY.map(function (n) {
      return '<div class="tog"><div class="txt"><strong>' + esc(n[0]) + "</strong><span>" +
        esc(n[1]) + '</span></div><label class="sw locked">' +
        '<input type="checkbox" checked disabled><i></i></label></div>';
    }).join("") +
    '<p class="necnote">These cannot be switched off, and we decide what goes in this ' +
      "list. Read the last four again: they are here because it suits us, not because " +
      "the marketplace stops working without them.</p>" +
    "</details>";
}

function wallV2(opts) {
  opts = opts || {};
  var inner = $("#wallInner"); inner.className = "wall-inner center";
  inner.innerHTML = "<h3>Your privacy choices</h3>" +
    '<div class="body"><p>We use cookies and similar technologies. Some are strictly ' +
      "necessary and are already on. The rest are optional and off until you say " +
      "otherwise.</p></div>" +
    necessaryBlock() +
    '<p class="optlabel">Optional purposes</p>' +
    "<div>" +
      tog("analytics", "Measure how the marketplace is used",
          "Aggregate page and collection statistics. Kept 14 months.") +
      tog("ads", "Show you relevant advertising", "Uses your activity on this site only.") +
      tog("profiling", "Build a profile and make predictions about you",
          "Includes guesses about your interests and circumstances.") +
      tog("share", "Share data with partners",
          "Two named recipients: NorthBeam Audiences Inc. (audience segments, " +
          "United States) and Adzumi DSP Ltd (ad selection, Ireland). " +
          "Named in full in the privacy notice.") +
    "</div>" +
    '<p class="socialproof">\u2728 <b>94% of visitors</b> accept all purposes. ' +
      "Accepting helps us keep the marketplace free.</p>" +
    '<div class="eq" style="margin-top:14px">' +
      '<button class="a" id="v2accept">Accept all<span class="recpill">Recommended</span></button>' +
      '<button class="r" id="v2save">Save my choices</button>' +
    "</div>" +
    '<button class="tiny-link" id="v2reject" style="margin-top:10px">Reject optional purposes</button>' +
    '<p class="vendorline" style="margin-top:8px">Strictly necessary purposes continue either ' +
      'way. You can reopen this from the cookie button at any time. ' +
      'Everyone who receives your data is named in the ' +
      '<a href="/privacy" target="_blank" rel="noopener">privacy notice</a>.</p>';
  $("#wall").classList.add("on");

  function save(vals, msg, thenNudge) {
    api("/api/consent", vals).then(function (e) {
      $("#wall").classList.remove("on"); applyEnvelope(e); toast(msg);
      if (thenNudge) setTimeout(nudgeV2, 2500);
    });
  }
  $("#v2accept").onclick = function () {
    save({ analytics: true, ads: true, profiling: true, share: true },
         "Saved. Reopen the cookie button to change it.");
  };
  $("#v2save").onclick = function () {
    save({ analytics: $("#t-analytics").checked, ads: $("#t-ads").checked,
           profiling: $("#t-profiling").checked, share: $("#t-share").checked },
         "Saved. Reopen the cookie button to change it.");
  };
  $("#v2reject").onclick = function () {
    save({ analytics: false, ads: false, profiling: false, share: false },
         "Optional purposes off. The necessary ones continue.", !opts.noNudge);
  };
}

/* The follow-up ask. Compliant sites do this too: the refusal is honoured, and
   then the question is put again in a friendlier shape a moment later. */
var nudged = false;
function nudgeV2() {
  if (nudged || ST.version !== 2) return;
  nudged = true;
  var n = $("#nag");
  n.innerHTML = "<strong>Just analytics?</strong>" +
    "No advertising, no profile, no partners. Only counts of which collections get " +
    "looked at. It genuinely helps us, and you can turn it off whenever you like." +
    '<div class="r"><button class="y" id="nudgeYes">Allow analytics</button>' +
    '<button class="tiny-link" id="nudgeNo">No thanks</button></div>';
  n.classList.add("on");
  $("#nudgeYes").onclick = function () {
    api("/api/consent", { analytics: true }).then(function (e) {
      applyEnvelope(e); n.classList.remove("on"); toast("Analytics on. Change it from the cookie button.");
    });
  };
  $("#nudgeNo").onclick = function () { n.classList.remove("on"); };
}

/* the cookie button: reopen the choices at any time, with the current state */
function openCookiePrefs() {
  wallV2({ noNudge: true });
  var c = ST.consent || {};
  ["analytics", "ads", "profiling", "share"].forEach(function (k) {
    var el = $("#t-" + k);
    if (el) el.checked = !!c[k];
  });
}


/* ====================== rights ====================== */
function sheet(title, art, body, foot) {
  $("#sheetBack").classList.add("on");
  $("#sheet").innerHTML = '<div class="sheet-head"><h3>' + title + '</h3><div class="art">' +
    art + '</div></div><div class="sheet-body">' + body + '</div><div class="sheet-foot">' +
    foot + "</div>";
}
function closeSheet() { $("#sheetBack").classList.remove("on"); }
function deadline() {
  return new Date(Date.now() + 30 * 864e5).toLocaleDateString(undefined,
    { day: "numeric", month: "long", year: "numeric" });
}

var RIGHTS = {
  inform: function () {
    api("/api/rights/informed").then(function (d) {
      sheet("What we collect, and why", "Articles 13 and 14 \u2014 right to be informed",
        "<p>This tab is how we meet this right: told plainly, at the time it happens, rather than " +
        "buried in a policy you have to go looking for. The list below is assembled live, so it " +
        "reflects what is actually happening right now, not what our policy permits.</p>" +
        '<ul class="rt-list">' + d.sections.map(function (s) {
          return "<li><b>" + esc(s.t) + "</b>" + esc(s.d) + "</li>";
        }).join("") + "</ul>",
        '<button class="sbtn pri" id="sClose">Close</button>');
      $("#sClose").onclick = closeSheet;
    });
  },
  access: function () {
    sheet("Get a copy of your data", "Article 15 \u2014 right of access",
      "<p>We will produce everything we hold, generated straight from the database, with a plain " +
      "explanation at the head of every section: what the data is, where it came from, and why we " +
      "have it.</p><div class=\"clock\">request logged " + new Date().toLocaleString() +
      "<br>statutory response deadline " + deadline() + " (one month)" +
      "<br>fee \u00a30.00 \u2014 a charge is unlawful for a first request</div>",
      '<button class="sbtn" id="sClose">Cancel</button>' +
      '<button class="sbtn pri" id="sGo">Download PDF</button>');
    $("#sClose").onclick = closeSheet;
    $("#sGo").onclick = function () {
      window.location = "/api/rights/sar.pdf"; closeSheet(); toast("Generating your access pack\u2026");
    };
  },
  port: function () {
    sheet("Export your data", "Article 20 \u2014 right to data portability",
      "<p>A structured, commonly used, machine-readable file you can hand to another marketplace. " +
      "It separates what you gave us from what we observed, because those are different things.</p>" +
      '<div class="clock">format JSON (UTF-8)<br>scope: data you provided and data observed from ' +
      "your activity<br>excludes: our derived inferences, which fall outside Art. 20</div>",
      '<button class="sbtn" id="sClose">Cancel</button>' +
      '<button class="sbtn pri" id="sGo">Download JSON</button>');
    $("#sClose").onclick = closeSheet;
    $("#sGo").onclick = function () {
      window.location = "/api/rights/export.json"; closeSheet();
    };
  },
  rect: function () {
    var id = (dossier.identity || {});
    var nm = [id.given_name, id.family_name].filter(Boolean).join(" ");
    sheet("Fix what is wrong", "Article 16 \u2014 right to rectification",
      "<p>Inaccurate data must be corrected without undue delay, and everyone we sent it to must " +
      "be told.</p>" +
      '<div class="ed"><label>name</label><input id="r-name" value="' + esc(nm) +
      '" placeholder="not supplied"></div>' +
      '<div class="ed"><label>email</label><input id="r-email" value="' + esc(id.email || "") +
      '" placeholder="not supplied"></div>' +
      '<p style="font-size:11.5px;color:var(--w-ink-soft);margin-top:12px">Inferences you disagree ' +
      "with cannot be edited here \u2014 they are opinions, not facts. Use Stop profiling to have " +
      "them deleted instead.</p>",
      '<button class="sbtn" id="sClose">Cancel</button>' +
      '<button class="sbtn pri" id="sGo">Save corrections</button>');
    $("#sClose").onclick = closeSheet;
    $("#sGo").onclick = function () {
      api("/api/rights/rectify", { name: $("#r-name").value, email: $("#r-email").value })
        .then(function (e) {
          applyEnvelope(e); closeSheet(); toast("Corrected. All recipients notified under Art. 19.");
        });
    };
  },
  object: function () {
    sheet("Stop profiling me", "Article 21 \u2014 right to object",
      "<p>For direct marketing there is no balancing test: you object, and it stops. Existing " +
      "inferences are deleted from the database, not merely hidden from you.</p>" +
      "<p>The marketplace keeps working. You will still see collections, just not ones chosen by " +
      "a model of you.</p>",
      '<button class="sbtn" id="sClose">Cancel</button>' +
      '<button class="sbtn dng" id="sGo">Stop profiling</button>');
    $("#sClose").onclick = closeSheet;
    $("#sGo").onclick = function () {
      api("/api/rights/object", {}).then(function (e) {
        applyEnvelope(e); closeSheet();
        toast("Profiling stopped. " + e.rows_dropped + " inference rows deleted.");
      });
    };
  },
  restrict: function () {
    var on = ST.restricted;
    sheet(on ? "Resume processing" : "Pause all processing",
      "Article 18 \u2014 right to restriction",
      on ? "<p>Processing is paused. The server is refusing optional telemetry outright. Lifting " +
           "the restriction resumes normal collection under your existing choices.</p>"
         : "<p>We will keep your data but stop using it, other than for storage \u2014 typically " +
           "while a dispute about accuracy or lawfulness is resolved.</p>" +
           '<div class="clock">stops: cursor telemetry, view and dwell history, search terms, ' +
           "scroll depth, tab focus, all inference<br>continues: your cart, your order records, " +
           "session integrity, security and fraud prevention<br>signal written to the profile: " +
           "USER SELECTED PAUSE.</div>" +
           "<p>Those continuing items are strictly necessary: without them the site cannot show " +
           "you your own cart or complete a mint you have already paid for.</p>",
      '<button class="sbtn" id="sClose">Cancel</button><button class="sbtn ' +
      (on ? "pri" : "dng") + '" id="sGo">' + (on ? "Resume" : "Pause processing") + "</button>");
    $("#sClose").onclick = closeSheet;
    $("#sGo").onclick = function () {
      api("/api/rights/restrict", {}).then(function (e) {
        applyEnvelope(e); closeSheet(); toast(e.signal);
      });
    };
  },
  auto: function () {
    var on = ST.automated_stopped;
    sheet(on ? "Resume automated decisions" : "Stop automated decisions",
      "Article 22 \u2014 automated decision-making and profiling",
      on ? "<p>Automated decision-making is switched off. Nothing is inferred about you and the " +
           "inferences table is empty. Resuming restarts the guessing.</p>"
         : "<p>You have the right to know the logic involved, and to demand a person instead of " +
           "an algorithm. Here, switching it off stops the model entirely.</p>" +
           '<div class="clock">stops: estimated age, inferred gender, household income, household ' +
           "composition, homeowner probability, health and mental health inference, life events, " +
           "financial stress index, political lean, religion cluster, interest segments<br>" +
           "continues: everything you actually did \u2014 views, searches, cart, orders<br>" +
           "signal written to the profile: USER SELECTED STOP.</div>" +
           "<p>This is narrower than pausing processing. We keep observing what you do; we stop " +
           "guessing who you are from it.</p>",
      '<button class="sbtn" id="sClose">Cancel</button>' +
      '<button class="sbtn ' + (on ? "pri" : "dng") + '" id="sGo">' +
      (on ? "Resume" : "Stop guessing") + "</button>" +
      (on ? "" : '<button class="sbtn" id="sHuman">Request human review</button>'));
    $("#sClose").onclick = closeSheet;
    if ($("#sHuman")) $("#sHuman").onclick = function () {
      closeSheet(); toast("Human review requested. A person will respond within 30 days.");
    };
    $("#sGo").onclick = function () {
      api("/api/rights/automated", {}).then(function (e) {
        applyEnvelope(e); closeSheet();
        toast(e.signal + (e.rows_dropped ? " " + e.rows_dropped + " rows deleted." : ""));
      });
    };
  },
  withdraw: function () {
    sheet("Withdraw your consent", "Article 7(3) \u2014 withdrawal",
      "<p>Withdrawal must be as easy as giving consent. It was one click to give, so it is one " +
      "click to take back.</p><p>Processing already carried out stays lawful; everything from this " +
      "moment stops, and derived data is deleted.</p>",
      '<button class="sbtn" id="sClose">Cancel</button>' +
      '<button class="sbtn dng" id="sGo">Withdraw consent</button>');
    $("#sClose").onclick = closeSheet;
    $("#sGo").onclick = function () {
      api("/api/rights/withdraw", {}).then(function (e) {
        applyEnvelope(e); closeSheet(); toast("Consent withdrawn. Effective immediately.");
      });
    };
  },
  complain: function () {
    sheet("All of your rights", "GDPR Chapter III, in plain words",
      '<ul class="rt-list">' + [
        ["Know what is happening", "Art. 13\u201314", "Told clearly, when data is collected. This tab."],
        ["Get a copy", "Art. 15", "Everything held about you, plus sources, recipients and retention."],
        ["Fix errors", "Art. 16", "Corrected without undue delay, and recipients told."],
        ["Be deleted", "Art. 17", "Erased, except where the law obliges us to keep something."],
        ["Pause us", "Art. 18", "Stored but not used, while a dispute runs."],
        ["Take it elsewhere", "Art. 20", "A machine-readable copy."],
        ["Say no", "Art. 21", "Absolute for direct marketing."],
        ["Not be decided about by machine alone", "Art. 22", "Demand human involvement."],
        ["Withdraw consent", "Art. 7(3)", "As easily as you gave it."],
        ["Complain", "Art. 77", "To your supervisory authority, free, without going through us."]
      ].map(function (r) {
        return "<li><b>" + r[0] + '</b><span class="a">' + r[1] + "</span> " + r[2] + "</li>";
      }).join("") + "</ul>" +
      '<div class="clock">Panopti Ltd is the controller. dpo@panopti.example<br>You may complain ' +
      "to your supervisory authority at any time. You do not need our permission and you do not " +
      "need to tell us.</div>",
      '<button class="sbtn pri" id="sClose">Close</button>');
    $("#sClose").onclick = closeSheet;
  },
  erase: function () {
    sheet("Delete everything", "Article 17 \u2014 right to erasure",
      "<p>This runs real DELETE statements against every table that holds you. It is not a flag on " +
      "a row. A small amount must lawfully survive, and we will name it rather than hide it.</p>" +
      '<div class="clock">this cannot be undone \u2014 the rows are gone<br>downstream recipients ' +
      "are notified under Art. 19<br>a suppression hash is kept so we never rebuild a profile of you</div>",
      '<button class="sbtn" id="sClose">Cancel</button>' +
      '<button class="sbtn dng" id="sGo">Delete everything</button>');
    $("#sClose").onclick = closeSheet;
    $("#sGo").onclick = runErasure;
  }
};

function runErasure() {
  api("/api/rights/erase/plan").then(function (plan) {
    var steps = plan.steps;
    sheet("Deleting your data", "Article 17 \u2014 erasure in progress",
      '<div class="pipe" id="pipe">' + steps.map(function (s, i) {
        return '<div id="pl' + i + '"><span class="st">\u00b7</span><span class="sys">' +
          esc(s.label) + '</span><span class="res" id="pr' + i + '"></span></div>';
      }).join("") + "</div>",
      '<button class="sbtn" id="sGo" disabled>Working\u2026</button>');
    var i = 0;
    (function step() {
      if (i >= steps.length) {
        var b = $("#sGo");
        if (b) {
          b.disabled = false; b.textContent = "Done"; b.className = "sbtn pri";
          b.onclick = function () {
            closeSheet();
            toast("Erased. Reloading as a stranger\u2026");
            // The server cleared the session cookie on the final step. There is no
            // in-session memory of an erased subject, so a reload starts collection
            // again from nothing, exactly as a first visit would.
            setTimeout(function () { location.reload(); }, 700);
          };
        }
        return;
      }
      api("/api/rights/erase/step", { index: i }).then(function (r) {
        var el = $("#pl" + i), res = $("#pr" + i);
        if (el) {
          el.classList.add("on");
          el.querySelector(".st").textContent = r.kind === "retain" ? "!" : "\u2713";
        }
        if (res) {
          res.textContent = r.kind === "retain" ? "RETAINED \u00b7 " + r.detail : r.detail;
          res.className = r.kind === "retain" ? "ret" : "res";
        }
        if (r.counts) renderDbGrid(r.counts);
        if (r.envelope) applyEnvelope(r.envelope);
        i++; setTimeout(step, 190);
      });
    })();
  });
}

var HUB = [
  ["inform", "Right to be informed", "Art. 13\u201314",
   "Clear, plain information about what we collect and why, given when it happens. This tab is how we do it.",
   "See what we collect now"],
  ["access", "Right of access", "Art. 15",
   "Ask for a copy of everything we hold about you. Free, and within a month.", "Get my copy (PDF)"],
  ["rect", "Right to rectification", "Art. 16",
   "Anything wrong or incomplete gets corrected, and everyone we sent it to is told.", "Fix my details"],
  ["erase", "Right to erasure", "Art. 17",
   "The right to be forgotten. Rows are dropped from the database, with only what the law forces us to keep left behind.",
   "Delete everything", true],
  ["restrict", "Right to restrict processing", "Art. 18",
   "Freeze what we do with your data while a dispute is sorted out. Necessary processing continues.",
   "Pause processing"],
  ["port", "Right to data portability", "Art. 20",
   "Take your data away in a readable file and use it with another service.", "Export my data"],
  ["object", "Right to object", "Art. 21",
   "Tell us to stop. For direct marketing there is no argument to be had: it stops.", "Stop profiling"],
  ["auto", "Automated decisions and profiling", "Art. 22",
   "Stop the algorithm guessing your age, gender and circumstances, or ask a person to review it.",
   "Stop automated decisions"]
];
function renderRights() {
  var host = $("#rhGrid"); if (!host) return;
  host.innerHTML = HUB.map(function (r) {
    var stateChip = "";
    var label = r[4];
    if (r[0] === "restrict" && ST.restricted) {
      stateChip = '<span class="state">USER SELECTED PAUSE.</span>'; label = "Resume processing";
    }
    if (r[0] === "auto" && ST.automated_stopped) {
      stateChip = '<span class="state">USER SELECTED STOP.</span>'; label = "Resume automated decisions";
    }
    if (r[0] === "object" && ST.objected) stateChip = '<span class="state">profiling stopped</span>';
    return '<article class="rh-card' + (r[5] ? " danger" : "") + '"><h3>' + esc(r[1]) + "</h3>" +
      '<span class="art">' + esc(r[2]) + "</span><p>" + esc(r[3]) + "</p>" + stateChip +
      '<button data-right="' + r[0] + '">' + esc(label) + "</button></article>";
  }).join("");
  $$("[data-right]").forEach(function (b) {
    b.onclick = function () {
      var r = b.dataset.right;
      if (ST.erased && r !== "complain" && r !== "inform") {
        toast("Nothing left to act on. Browse again to start over."); return;
      }
      if (RIGHTS[r]) RIGHTS[r]();
    };
  });
}

/* ====================== telemetry ====================== */
function track() {
  var lx = null, ly = null, lastT = 0, lastClick = 0, run = 0;
  document.addEventListener("mousemove", function (e) {
    var now = performance.now();
    P.x = e.clientX; P.y = e.clientY;
    if (lx !== null) {
      var dx = e.clientX - lx, dy = e.clientY - ly, dist = Math.sqrt(dx * dx + dy * dy);
      P.travel += dist;
      var dt = (now - lastT) / 1000;
      if (dt > 0) P.speed = P.speed * 0.8 + (dist / dt) * 0.2;
    }
    lx = e.clientX; ly = e.clientY; lastT = now; P.samples++;
  }, { passive: true });
  document.addEventListener("click", function () {
    P.clicks++;
    var now = Date.now();
    if (now - lastClick < 420) { run++; if (run >= 2) P.rage++; } else run = 0;
    lastClick = now;
  }, { passive: true });
  document.addEventListener("copy", function () { P.copies++; });
  document.addEventListener("keydown", function (e) {
    P.keys++; if (e.key === "Backspace") P.backspaces++;
  }, { passive: true });
  var lastBlur = 0;
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) { lastBlur = Date.now(); P.blurs++; }
    else if (lastBlur) { P.blurMs += Date.now() - lastBlur; lastBlur = 0; }
  });
  function onScroll(el) {
    var pct = (el.scrollTop + el.clientHeight) / el.scrollHeight * 100;
    if (pct > P.scroll) P.scroll = Math.min(100, pct);
  }
  $("#shopPane").addEventListener("scroll", function (e) { onScroll(e.target); }, { passive: true });
  window.addEventListener("scroll", function () {
    var pct = (window.scrollY + window.innerHeight) / document.body.scrollHeight * 100;
    if (pct > P.scroll) P.scroll = Math.min(100, pct);
  }, { passive: true });

  var hoverId = null, hoverStart = 0;
  var host = $("#collections");
  host.addEventListener("mouseover", function (e) {
    var card = e.target.closest(".card");
    if (!card || card.dataset.id === hoverId) return;
    hoverId = card.dataset.id; hoverStart = Date.now();
  });
  host.addEventListener("mouseout", function (e) {
    var card = e.target.closest(".card");
    if (!card || !hoverId) return;
    if (e.relatedTarget && card.contains(e.relatedTarget)) return;
    var ms = Date.now() - hoverStart;
    var v = pendingViews[hoverId] || { v: 0, d: 0 };
    v.d += ms;
    if (ms > 700) v.v += 1;
    pendingViews[hoverId] = v;
    hoverId = null;
  });
  host.addEventListener("click", function (e) {
    var add = e.target.closest("[data-add]");
    if (add) {
      api("/api/cart", { token_id: add.dataset.add, op: "add" }).then(function (en) {
        applyEnvelope(en);
        toast((PRODUCTS[add.dataset.add] || {}).n + " queued to mint");
        if (ST.version === 1) maybeNag();
      });
      return;
    }
    var adgo = e.target.closest("[data-adgo]");
    if (adgo) { convert(adgo.dataset.adgo); return; }
    var adcard = e.target.closest(".adcard");
    if (adcard) { convert(adcard.dataset.adid); return; }

    var card = e.target.closest(".card");
    if (card && card.dataset.id) { openToken(card.dataset.id); }
    if (card && card.dataset.id) {
      var v = pendingViews[card.dataset.id] || { v: 0, d: 0 };
      v.v += 1; v.d += 900; pendingViews[card.dataset.id] = v;
    }
  });
}

function beacon() {
  var hasT = Object.keys(P).some(function (k) { return P[k]; });
  var body = { t: Object.assign({}, P), views: pendingViews,
               searches: pendingSearches, events: pendingEvents };
  var counters = ["travel", "samples", "clicks", "rage", "keys", "backspaces", "copies", "blurs", "blurMs"];
  counters.forEach(function (k) { P[k] = 0; });
  pendingViews = {}; pendingSearches = []; pendingEvents = [];
  if (!hasT && !Object.keys(body.views).length && !body.searches.length) {
    body.t = { x: P.x, y: P.y };
  }
  api("/api/track", body).then(applyEnvelope).catch(function () {});
}

/* ====================== wiring ====================== */
function showTab(which) {
  document.body.dataset.tab = which;
  $("#viewMarket").hidden = which !== "market";
  $("#viewRights").hidden = which !== "rights";
  $("#tabMarket").setAttribute("aria-selected", String(which === "market"));
  $("#tabRights").setAttribute("aria-selected", String(which === "rights"));
}

function openWall() {
  setTimeout(function () { ST.version === 1 ? wallV1() : wallV2(); },
             ST.version === 1 ? 900 : 1400);
}

function init() {
  initA11y(); initPaneControls(); loadAd(); startLogPolling();
  renderGrid(); renderRights(); track();
  showTab("market");

  var dev = collectDevice();
  api("/api/device", dev).then(applyEnvelope);

  $("#search").addEventListener("input", function (e) {
    search = e.target.value; renderGrid();
    clearTimeout(window.__sq);
    window.__sq = setTimeout(function () {
      var q = search.trim();
      if (q.length > 1 && pendingSearches[pendingSearches.length - 1] !== q) pendingSearches.push(q);
    }, 600);
  });
  $("#openCart").onclick = openDrawer;
  $("#closeCart").onclick = closeDrawer;
  $("#drawerBack").onclick = closeDrawer;
  $("#sheetBack").onclick = function (e) { if (e.target === $("#sheetBack")) closeSheet(); };
  $("#modalBack").onclick = function (e) {
    if (e.target === $("#modalBack")) $("#modalBack").classList.remove("on");
  };
  $("#v1").onclick = function () { switchVersion(1); };
  $("#v2").onclick = function () { switchVersion(2); };
  $("#resetBtn").onclick = function () {
    api("/api/reset", {}).then(function (e) {
      firstRender = true; started = Date.now(); minuteClock = 0; nagCount = 0;
      applyEnvelope(e); showTab("market"); reseedDevice();
      toast("Session reset"); openWall();
    });
  };
  $("#tabMarket").onclick = function () { showTab("market"); };
  $("#tabRights").onclick = function () { showTab("rights"); };
  $("#paneShop").onclick = function () {
    document.body.dataset.pane = "shop";
    $("#paneShop").setAttribute("aria-pressed", "true");
    $("#paneWatch").setAttribute("aria-pressed", "false");
  };
  $("#paneWatch").onclick = function () {
    document.body.dataset.pane = "watch";
    $("#paneWatch").setAttribute("aria-pressed", "true");
    $("#paneShop").setAttribute("aria-pressed", "false");
  };
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      closeToken(); closeSheet(); $("#modalBack").classList.remove("on"); closeDrawer(); }
  });

  setInterval(beacon, 1200);
  /* the clock ticks once a minute; the cursor updates on every beacon */
  setInterval(function () {
    minuteClock = Math.floor((Date.now() - started) / 60000);
    $("#stTime").textContent = minuteClock + " min";
  }, 60000);

  openWall();
}

function reseedDevice() {
  /* A reset drops every table, including the device row. Device and network
     data is strictly necessary collection, so it resumes immediately — the
     panel would otherwise imply that resetting stopped it, which is the one
     thing it never does. */
  try { api("/api/device", collectDevice()).then(applyEnvelope); } catch (e) {}
}

function switchVersion(v) {
  api("/api/version", { version: v }).then(function (e) {
    firstRender = true; started = Date.now(); minuteClock = 0; nagCount = 0;
    $("#stTime").textContent = "0 min";
    $("#search").value = ""; search = ""; renderGrid();
    $("#nag").classList.remove("on");
    closeDrawer(); closeSheet();
    applyEnvelope(e); showTab("market"); reseedDevice(); openWall();
  });
}

/* ------------------------ browser fingerprint ------------------------ */
function hash(str) {
  var h = 2166136261;
  for (var i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return (h >>> 0).toString(16);
}
function collectDevice() {
  var ua = navigator.userAgent;
  var tz = (Intl.DateTimeFormat().resolvedOptions().timeZone) || "unknown";
  var fp = "blocked", gl = { vendor: "unavailable", renderer: "unavailable" };
  try {
    var c = document.createElement("canvas"); c.width = 260; c.height = 60;
    var x = c.getContext("2d");
    x.textBaseline = "top"; x.font = '16px "Arial"';
    x.fillStyle = "#f60"; x.fillRect(0, 0, 120, 30);
    x.fillStyle = "#069"; x.fillText("panopti fp 9.7", 2, 15);
    fp = hash(c.toDataURL()).slice(0, 12);
  } catch (e) {}
  try {
    var gc = document.createElement("canvas").getContext("webgl");
    if (gc) {
      var dbg = gc.getExtension("WEBGL_debug_renderer_info");
      gl = { vendor: dbg ? gc.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : gc.getParameter(gc.VENDOR),
             renderer: dbg ? gc.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gc.getParameter(gc.RENDERER) };
    }
  } catch (e) {}
  var fonts = [];
  try {
    var base = ["monospace", "sans-serif", "serif"];
    var test = ["Helvetica Neue", "Georgia", "Garamond", "Palatino", "Futura", "Optima",
      "Gill Sans", "Courier New", "Segoe UI", "Calibri", "Cambria", "Tahoma", "Verdana",
      "Impact", "Comic Sans MS", "Menlo", "Consolas", "SF Pro Text"];
    var span = document.createElement("span");
    span.style.cssText = "position:absolute;left:-9999px;font-size:72px;white-space:nowrap";
    span.textContent = "mmmmmmmmmmlli";
    document.body.appendChild(span);
    var ref = {};
    base.forEach(function (b) { span.style.fontFamily = b; ref[b] = [span.offsetWidth, span.offsetHeight]; });
    test.forEach(function (f) {
      for (var i = 0; i < base.length; i++) {
        span.style.fontFamily = '"' + f + '",' + base[i];
        if (span.offsetWidth !== ref[base[i]][0] || span.offsetHeight !== ref[base[i]][1]) {
          fonts.push(f); break;
        }
      }
    });
    span.remove();
  } catch (e) {}
  var CITY = {
    "America/Denver": ["Denver, Colorado", "US", "80129"],
    "America/New_York": ["New York, New York", "US", "10001"],
    "America/Chicago": ["Chicago, Illinois", "US", "60601"],
    "America/Los_Angeles": ["Los Angeles, California", "US", "90001"],
    "Europe/London": ["London", "GB", "EC1A"], "Europe/Dublin": ["Dublin", "IE", "D01"],
    "Europe/Berlin": ["Berlin", "DE", "10115"], "Europe/Paris": ["Paris", "FR", "75001"],
    "Europe/Madrid": ["Madrid", "ES", "28001"], "Europe/Amsterdam": ["Amsterdam", "NL", "1011"],
    "Asia/Tokyo": ["Tokyo", "JP", "100-0001"], "Asia/Kolkata": ["Mumbai", "IN", "400001"],
    "Australia/Sydney": ["Sydney", "AU", "2000"]
  };
  var city = CITY[tz] || [tz.split("/").pop().replace(/_/g, " "), "\u2014", "\u2014"];
  function bn() {
    var m = /Edg\/([\d.]+)/.exec(ua) ? ["Edge", RegExp.$1]
      : /OPR\/([\d.]+)/.exec(ua) ? ["Opera", RegExp.$1]
      : /Firefox\/([\d.]+)/.exec(ua) ? ["Firefox", RegExp.$1]
      : /Chrome\/([\d.]+)/.exec(ua) ? ["Chrome", RegExp.$1]
      : /Version\/([\d.]+).*Safari/.exec(ua) ? ["Safari", RegExp.$1] : ["Unknown", "0"];
    return m[0] + " " + m[1];
  }
  function os() {
    if (/Windows NT 10/.test(ua)) return "Windows 10 or 11";
    if (/Mac OS X ([\d_]+)/.test(ua)) return "macOS " + RegExp.$1.replace(/_/g, ".");
    if (/Android ([\d.]+)/.test(ua)) return "Android " + RegExp.$1;
    if (/iPhone OS ([\d_]+)/.test(ua)) return "iOS " + RegExp.$1.replace(/_/g, ".");
    if (/Linux/.test(ua)) return "Linux";
    return "Unknown";
  }
  var touch = navigator.maxTouchPoints || 0;
  var d = {
    ua: ua, browser: bn(), os: os(),
    languages: (navigator.languages || [navigator.language]).slice(0, 4),
    tz: tz, city: city[0], country: city[1], postal: city[2],
    screen: screen.width + "\u00d7" + screen.height,
    viewport: window.innerWidth + "\u00d7" + window.innerHeight,
    dpr: window.devicePixelRatio || 1, colorDepth: screen.colorDepth,
    cores: navigator.hardwareConcurrency || null, memGB: navigator.deviceMemory || null,
    touch: touch,
    deviceClass: touch > 0 ? (Math.min(screen.width, screen.height) < 500 ? "smartphone" : "tablet")
                           : "desktop or laptop",
    canvasFP: fp, glVendor: gl.vendor, glRenderer: gl.renderer,
    fonts: fonts.length ? fonts : ["(none detected)"],
    darkMode: matchMedia("(prefers-color-scheme: dark)").matches,
    cookiesEnabled: navigator.cookieEnabled,
    dnt: navigator.doNotTrack === "1" || window.doNotTrack === "1",
    gpc: !!navigator.globalPrivacyControl,
    referrer: document.referrer || "(direct / none)",
    conn: navigator.connection ? { type: navigator.connection.effectiveType,
                                   downlinkMbps: navigator.connection.downlink } : null,
    battery: null,
    localTimeOffset: -new Date().getTimezoneOffset() / 60
  };
  d.fingerprintId = hash(fp + gl.renderer + d.screen + fonts.join() + tz).slice(0, 10).toUpperCase();
  if (navigator.getBattery) {
    navigator.getBattery().then(function (b) {
      d.battery = { level: Math.round(b.level * 100) + "%", charging: b.charging };
      api("/api/device", d).then(applyEnvelope);
    }).catch(function () {});
  }
  return d;
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
else init();
})();
