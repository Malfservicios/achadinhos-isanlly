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
        "narracao_gancho": {"type": "string",
                            "description": "abertura falada do vídeo, 4 a 7 palavras, animada, sem emoji (ex.: 'Gente, olha esse achadinho!')"},
        "narracao_descricao": {"type": "string",
                               "description": "2 frases curtas faladas descrevendo o produto e por que vale a pena, "
                                              "18 a 28 palavras no total, sem emoji, sem preço, sem números difíceis de ler"},
    },
    "required": ["chamada", "nome_curto", "beneficios", "fechamento", "narracao_gancho", "narracao_descricao"],
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


GANCHOS = ["Gente, olha esse achadinho!", "Achei uma oferta muito boa!", "Olha o que eu encontrei pra vocês!",
           "Esse achadinho vale a pena!"]


def _nome_falado(titulo, palavras=7):
    """Primeiras palavras do titulo, sem numeros/medidas no fim (soa melhor falado)."""
    import re
    titulo = re.sub(r"(?<=[A-Za-zÀ-ú])(?=\d)|(?<=\d)(?=[A-Za-zÀ-ú])", " ", titulo)  # "Bluetooth6.0" -> "Bluetooth 6.0"
    p = titulo.split()[:palavras]
    soltas = {"e", "de", "da", "do", "das", "dos", "com", "para", "pra", "em", "a", "o", "-", "+", "/"}
    while len(p) > 3 and (any(ch.isdigit() for ch in p[-1]) or p[-1].lower() in soltas):
        p.pop()
    return " ".join(p)


def _criativo_padrao(p):
    rnd = random.Random(p["ml_id"])
    nome = p["titulo"] if len(p["titulo"]) <= 60 else p["titulo"][:57].rsplit(" ", 1)[0] + "…"
    return {"chamada": rnd.choice(CHAMADAS), "nome_curto": nome, "beneficios": [],
            "fechamento": rnd.choice(FECHAMENTOS),
            "narracao_gancho": rnd.choice(GANCHOS),
            "narracao_descricao": f"{_nome_falado(p['titulo'], 5)}. Um achadinho muito bem avaliado no Mercado Livre."}


def _reais_falado(v, com_moeda=True):
    """Como se fala no Brasil: '79 reais e 90' / '119 e 90' (sem 'centavos', mais curto)."""
    inteiro, cent = int(v), round((v - int(v)) * 100)
    txt = f"{inteiro} {'real' if inteiro == 1 else 'reais'}" if com_moeda or not cent else str(inteiro)
    return f"{txt} e {cent}" if cent else txt


CTAS = ["O link está aqui na mensagem. Corre que acaba rápido!", "Toca no link da mensagem e garante o seu!",
        "O link está aqui embaixo. Aproveita!"]


def roteiro_narracao(p, c):
    """Narracao do video em blocos (cada bloco casa com uma cena)."""
    rnd = random.Random(p["ml_id"] + "cta")
    if p.get("preco") is None:
        preco = "O preço atualizado está no link."
    elif p.get("preco_original"):
        preco = f"De {_reais_falado(p['preco_original'], False)}, por apenas {_reais_falado(p['preco'])}!"
    else:
        preco = f"Está saindo por {_reais_falado(p['preco'])}."
    if p.get("frete_gratis"):
        preco += " E com frete grátis!"
    return {
        "gancho": c.get("narracao_gancho") or GANCHOS[0],
        "descricao": c.get("narracao_descricao") or f"É o {_nome_falado(p['titulo'])}.",
        "preco": preco,
        "cta": rnd.choice(CTAS),
    }


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
