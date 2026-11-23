// Painel dos Achadinhos: lista os posts gerados e ajuda a publicar no WhatsApp.
const REPO = "Malfservicios/achadinhos-isanlly";
const URL_WORKFLOW_LINKS = `https://github.com/${REPO}/actions/workflows/gerar.yml`;
const URL_WORKFLOW_CONECTAR = `https://github.com/${REPO}/actions/workflows/conectar-ml.yml`;

const $ = (s, el = document) => el.querySelector(s);
let filtro = "novos";
let posts = [];

// ---- armazenamento local (so neste celular) ----
const guardar = {
  ler(chave, padrao) { try { return JSON.parse(localStorage.getItem(chave)) ?? padrao; } catch { return padrao; } },
  salvar(chave, valor) { try { localStorage.setItem(chave, JSON.stringify(valor)); } catch { /* modo privado */ } },
};
let publicados = guardar.ler("publicados", {});
let edicoes = guardar.ler("edicoes", {});

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("on");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("on"), 2600);
}

async function copiar(texto) {
  try { await navigator.clipboard.writeText(texto); return true; }
  catch {
    const ta = document.createElement("textarea");
    ta.value = texto; document.body.append(ta); ta.select();
    const ok = document.execCommand("copy"); ta.remove(); return ok;
  }
}

function quando(iso) {
  const d = new Date(iso);
  const hoje = new Date();
  const ontem = new Date(Date.now() - 864e5);
  const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  if (d.toDateString() === hoje.toDateString()) return `hoje ${hora}`;
  if (d.toDateString() === ontem.toDateString()) return `ontem ${hora}`;
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" }) + " " + hora;
}

async function arquivo(url, nome) {
  const r = await fetch(url);
  if (!r.ok) throw new Error("download falhou");
  const blob = await r.blob();
  return new File([blob], nome, { type: blob.type });
}

// ---- cartoes ----
function montarCard(p) {
  const el = $("#tpl-card").content.firstElementChild.cloneNode(true);
  const img = $("img", el), video = $("video", el), ta = $("textarea", el);
  let midia = "imagem";
  img.src = p.imagem;
  img.alt = p.titulo;
  $("h3", el).textContent = p.nome_curto || p.titulo;
  $(".cat", el).textContent = p.categoria || "Achadinho";
  $(".quando", el).textContent = quando(p.criado_em);
  ta.value = edicoes[p.id] ?? p.texto;
  const btnRestaurar = $('[data-acao="restaurar"]', el);
  btnRestaurar.hidden = !(p.id in edicoes);

  if (p.video) {
    const alt = $(".alternar", el);
    alt.hidden = false;
    alt.addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      midia = b.dataset.midia;
      alt.querySelectorAll("button").forEach((x) => x.classList.toggle("ativo", x === b));
      const ehVideo = midia === "video";
      if (ehVideo && !video.src) { video.src = p.video; video.poster = p.imagem; }
      video.hidden = !ehVideo; img.hidden = ehVideo;
      if (ehVideo) video.play().catch(() => {}); else video.pause();
    });
  }

  ta.addEventListener("input", () => {
    edicoes[p.id] = ta.value; guardar.salvar("edicoes", edicoes); btnRestaurar.hidden = false;
  });

  const marcar = (sim) => {
    if (sim) publicados[p.id] = Date.now(); else delete publicados[p.id];
    guardar.salvar("publicados", publicados);
    el.classList.toggle("feito", !!sim);
    $('[data-acao="publicado"]', el).textContent = sim ? "↩️ Voltar para publicar" : "✅ Marcar como publicado";
  };
  marcar(!!publicados[p.id]);

  el.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-acao]"); if (!b) return;
    const texto = ta.value;
    const url = midia === "video" ? p.video : p.imagem;
    const nome = `${p.id}.${midia === "video" ? "mp4" : "jpg"}`;
    switch (b.dataset.acao) {
      case "copiar":
        toast((await copiar(texto)) ? "Texto copiado! É só colar no WhatsApp 💛" : "Não consegui copiar 😕");
        break;
      case "baixar": {
        const a = document.createElement("a");
        a.href = url; a.download = nome; document.body.append(a); a.click(); a.remove();
        toast(midia === "video" ? "Baixando o vídeo…" : "Baixando a foto…");
        break;
      }
      case "compartilhar": {
        // Copia o texto antes: se o app nao colar a legenda sozinho, e so colar.
        await copiar(texto);
        try {
          const f = await arquivo(url, nome);
          if (navigator.canShare && navigator.canShare({ files: [f] })) {
            await navigator.share({ files: [f], text: texto });
            marcar(true);
          } else {
            window.open("https://wa.me/?text=" + encodeURIComponent(texto), "_blank");
            toast("Seu navegador não envia foto direto: baixe a foto e cole o texto.");
          }
        } catch (err) {
          if (err && err.name === "AbortError") return; // cancelou
          window.open("https://wa.me/?text=" + encodeURIComponent(texto), "_blank");
        }
        break;
      }
      case "publicado":
        marcar(!publicados[p.id]);
        if (filtro !== "todos") setTimeout(render, 300);
        break;
      case "restaurar":
        delete edicoes[p.id]; guardar.salvar("edicoes", edicoes);
        ta.value = p.texto; btnRestaurar.hidden = true;
        break;
    }
  });
  return el;
}

function render() {
  const lista = $("#lista");
  lista.replaceChildren();
  const visiveis = posts.filter((p) =>
    filtro === "todos" ? true : filtro === "publicados" ? publicados[p.id] : !publicados[p.id]);
  $("#status").textContent = visiveis.length
    ? `${visiveis.length} post(s)`
    : filtro === "novos" ? "Tudo publicado por aqui ✨ Novos achadinhos chegam às 10h e às 17h." : "Nada por aqui ainda.";
  visiveis.forEach((p) => lista.append(montarCard(p)));
}

async function carregar() {
  try {
    const r = await fetch("posts.json?t=" + Date.now(), { cache: "no-store" });
    posts = r.ok ? await r.json() : [];
  } catch { posts = []; }
  render();
}

// ---- filtros e links ----
document.querySelector(".filtros").addEventListener("click", (e) => {
  const b = e.target.closest("[data-filtro]"); if (!b) return;
  filtro = b.dataset.filtro;
  document.querySelectorAll("[data-filtro]").forEach((x) => x.classList.toggle("ativo", x === b));
  render();
});
$("#link-novo").href = URL_WORKFLOW_LINKS;
$("#link-conectar").href = URL_WORKFLOW_CONECTAR;

// Volta da autorizacao do Mercado Livre: mostra o codigo para copiar.
const codigo = new URLSearchParams(location.search).get("code");
if (codigo) {
  $("#conectar").hidden = false;
  $("#codigo").textContent = codigo;
  $("[data-copiar-codigo]").addEventListener("click", async () => toast((await copiar(codigo)) ? "Código copiado!" : "Copie manualmente"));
}

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
carregar();
