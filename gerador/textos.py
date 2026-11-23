"""Texto do post para WhatsApp.

O Claude escreve so a parte criativa (chamada + beneficios). Preco, link e
avisos sao montados aqui, para nunca sair um preco inventado.
Sem ANTHROPIC_API_KEY (ou se a API falhar) usa frases prontas.
"""
import json
import os
import random

from .comum import CONFIG, agora, reais

ESTILO = """Você escreve os posts do grupo de WhatsApp "Os Achadinhos da Isanlly", onde a Isanlly
indica produtos do Mercado Livre. Voz: uma amiga animada e confiável que achou uma oferta
boa e quer contar — calorosa, leve, direta, português do Brasil, sem exagero e sem
promessas falsas. Nunca invente características que não estejam nos dados do produto.
Nunca mencione preços, porcentagens ou frete (isso é colocado depois automaticamente)."""

ESQUEMA = {
    "type": "object",
    "properties": {
        "chamada": {"type": "string", "description": "1 linha curta e chamativa, com 1 emoji no início"},
        "nome_curto": {"type": "string", "description": "nome do produto resumido (máx. 60 caracteres)"},
        "beneficios": {"type": "array", "items": {"type": "string"},
                       "description": "3 benefícios curtos (máx. 55 caracteres cada), sem emoji"},
        "fechamento": {"type": "string", "description": "1 frase curta convidando a aproveitar"},
    },
    "required": ["chamada", "nome_curto", "beneficios", "fechamento"],
    "additionalProperties": False,
}

CHAMADAS = ["🔥 Achadinho do dia!", "✨ Olha o que eu achei pra vocês!", "😍 Esse eu precisava mostrar!",
            "🛍️ Achadinho que vale a pena!", "💥 Preço bom demais pra deixar passar!"]
FECHAMENTOS = ["Corre que oferta boa não dura muito! 🏃‍♀️", "Aproveita enquanto está com esse preço! 💛",
               "Depois não diz que eu não avisei! 😉", "Garante o seu antes que acabe! ✨"]


def _criativo_claude(p):
    import anthropic

    cliente = anthropic.Anthropic()
    dados = {"titulo": p["titulo"], "categoria": p.get("categoria", ""), "atributos": p.get("atributos", [])}
    pedido = dict(
        model=CONFIG["texto"]["modelo_claude"],
        max_tokens=4000,
        system=ESTILO,
        output_config={"effort": CONFIG["texto"].get("esforco", "low"),
                       "format": {"type": "json_schema", "schema": ESQUEMA}},
        messages=[{"role": "user", "content": "Dados do produto:\n" + json.dumps(dados, ensure_ascii=False)}],
    )
    try:
        # Se o modelo recusar, a API refaz o pedido num modelo alternativo.
        r = cliente.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **pedido)
    except (anthropic.BadRequestError, TypeError):  # SDK/conta sem o recurso de fallback
        r = cliente.messages.create(**pedido)
    if r.stop_reason == "refusal":
        raise RuntimeError("Claude recusou o pedido")
    texto = next(b.text for b in r.content if b.type == "text")
    return json.loads(texto)


def _criativo_padrao(p):
    rnd = random.Random(p["ml_id"])
    nome = p["titulo"] if len(p["titulo"]) <= 60 else p["titulo"][:57].rsplit(" ", 1)[0] + "…"
    return {"chamada": rnd.choice(CHAMADAS), "nome_curto": nome, "beneficios": [],
            "fechamento": rnd.choice(FECHAMENTOS)}


def criativo(p):
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _criativo_claude(p)
        except Exception as e:  # noqa: BLE001 - o post sai com o texto padrao
            print(f"  [texto] Claude falhou ({type(e).__name__}: {e}); usando texto padrao")
    return _criativo_padrao(p)


def montar_texto(p, c):
    """Formatacao do WhatsApp: *negrito*, _italico_, ~riscado~."""
    linhas = [f"*{c['chamada']}*", "", f"🛒 *{c['nome_curto']}*"]
    for b in c.get("beneficios", [])[:3]:
        linhas.append(f"✔️ {b}")
    linhas.append("")
    if p.get("preco") is not None:
        if p.get("preco_original"):
            linhas.append(f"De ~{reais(p['preco_original'])}~")
            linhas.append(f"💰 Por *{reais(p['preco'])}*  ({p['desconto']}% OFF)")
        else:
            linhas.append(f"💰 Por *{reais(p['preco'])}*")
        if p.get("frete_gratis"):
            linhas.append("🚚 Frete grátis")
        linhas.append("")
    linhas.append(c["fechamento"])
    linhas.append(f"👉 {p['link']}")
    linhas.append("")
    if p.get("preco") is not None:
        linhas.append(f"_Preço visto em {agora():%d/%m às %Hh%M}, pode mudar a qualquer momento._")
    linhas.append("_Link de afiliada: comprando por ele você ajuda o grupo, sem pagar nada a mais._ 💛")
    return "\n".join(linhas)
